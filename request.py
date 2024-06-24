import os
import subprocess

import requests

import helpers


class McmRequest:
    request_id = ""
    RequestConfig = {
        "cmssw": "",
        "driverCommand": [],
        "arch": "",
        "fragment": "",
        "fragmentPath": "",
    }

    def __init__(self, config_data, debug=False):
        self.debug = debug
        if not helpers.validate_config(config_data):
            raise Exception("Yaml config is not correct ! Pls fix")
        self.request_id = config_data["request_id"]
        self.label = config_data["label"]
        self.workdir = os.path.abspath("workdirs/" + config_data["workdir"])
        self.batch_system = config_data["batch_system"]
        self.input_files = config_data["input_files"]
        self.events_per_job = config_data["events_per_job"]
        self.cpus_per_job = config_data.get("cpus_per_job", 1)
        self.output_path = config_data["output_path"]
        self.total_events = config_data["total_events"]
        self.tasks = []
        self.gc_parameters = {
            "workdir": self.workdir + "/gc_workdir",
            "jobs": (
                f"jobs = {int(self.total_events / self.events_per_job)}"
                if not self.input_files
                else ""
            ),  # only set number of jobs if no input files are given which happens in the first step of the simulation chain
            "config_file": "",
            "events_per_job": str(self.events_per_job),
            "se_output_files": "",
            "se_output_pattern": self.label + "/",
            "se_path": str(self.output_path),
            "cpus": str(self.cpus_per_job),
            "dataset": "",
            "accounting_group": config_data.get("accounting_group", "cms.higgs"),
            "scratch_space_used": config_data.get("scratch_space_used", "7500"),
        }

    def setup_all(self):
        """
        run all nessessay steps
        """

        print(
            f"""Create config for {self.request_id}
        label: {self.label}
        input_files: {self.input_files}
        output_path: {self.output_path}
        workdir: {self.workdir}
        batch_system: {self.batch_system}
        events_per_job: {self.events_per_job}
        total_events: {self.total_events}
        cpus_per_job: {self.cpus_per_job}
        accounting_group: {self.gc_parameters["accounting_group"]}"""
        )
        self.get_mcm_setup()
        self.setup_cmssw()
        self.generate_gc_config()
        self.modify_cmsRun_for_gc()
        self.finalize()

    def get_mcm_setup(self):
        """
        get setup script from McM
        """
        url = "https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_setup/{request}".format(
            request=self.request_id
        )
        if self.debug:
            print(f" Get Setup script from McM: {url}")
        setup = requests.get(url, verify=False)

        # parse setup script to get CMSSW version, architecture, fragment and cmsDriver command
        for line in setup.text.split("\n"):
            if "ARCH" in line and self.RequestConfig["arch"] == "":
                self.RequestConfig["arch"] = [s for s in line.split("=") if "gcc" in s][
                    0
                ]
            if "scram" in line and self.RequestConfig["cmssw"] == "":
                self.RequestConfig["cmssw"] = [
                    s for s in line.split(" ") if "CMSSW_" in s
                ][0]
            if "get_fragment" in line:
                self.RequestConfig["fragment"] = [
                    s for s in line.split(" ") if "https" in s
                ][0]
                self.RequestConfig["fragmentPath"] = [
                    s for s in line.split(" ") if "fragment.py" in s
                ][0]
            if "cmsDriver.py" in line:
                self.RequestConfig["driverCommand"].append(line)

    def setup_cmssw(self):
        """
        setup CMSSW workdir
        """
        if self.debug:
            print(f"Create initial and working scripts and fill it with cmssw setup")
        helpers.createFolder(self.workdir)
        f_initial = open("{}/{}_initial.sh".format(self.workdir, self.label), "w+")
        f_working = open("{}/{}_working.sh".format(self.workdir, self.label), "w+")

        f_initial.write("#!/bin/bash\n")
        f_working.write("#!/bin/bash\n")

        if helpers.createFolder(
            os.path.join(self.workdir, self.RequestConfig["cmssw"], "src")
        ):
            helpers.initiate_cmssw(
                self.workdir,
                self.RequestConfig["cmssw"],
                self.RequestConfig["arch"],
                f_initial,
                f_working,
            )
        else:
            print("WARNING: Workdir is already setup")

        # downlaod fragment script if needed
        if self.RequestConfig["fragment"] != "":
            helpers.getFragment(
                self.request_id,
                self.RequestConfig["fragment"],
                os.path.join(
                    self.workdir,
                    self.RequestConfig["cmssw"],
                    "src",
                    self.RequestConfig["fragmentPath"],
                ),
            )
        # write cmssw setup to initial and working script
        helpers.scram(
            os.path.join(self.workdir, self.RequestConfig["cmssw"]),
            f_initial,
            f_working,
        )

        # update the cmsDriver command with the correct input and output paths
        for i, driver in enumerate(self.RequestConfig["driverCommand"]):
            self.tasks.append(
                helpers.updateDriverCommands(
                    i,
                    driver,
                    self.events_per_job,
                    self.label,
                    f_initial,
                    self.cpus_per_job,
                    debug=self.debug,
                )
            )
        # construct dict for gc config file
        self.gc_parameters["config_file"] = " ".join(self.tasks)
        self.gc_parameters["se_output_files"] = self.tasks[-1].replace(
            "_cfg.py", ".root"
        )
        # check if input file is a dbs link or a filelist
        if self.input_files != "":
            if os.path.isfile(self.input_files):
                self.gc_parameters["dataset"] = (
                    f"dataset = {self.label} : list:{self.input_files}"
                )
            elif len(self.input_files.split("/")) == 4:
                self.gc_parameters["dataset"] = (
                    f"dataset = {self.label} : {self.input_files}"
                )
            else:
                raise Exception(f"{self.input_files} is not a valid Inputfile !")
        # close files and make them executable
        f_initial.close()
        f_working.close()
        os.chmod(f"{self.workdir}/{self.label}_initial.sh", 0o744)
        # run the setup shell script
        process = subprocess.Popen(
            f"./{self.label}_initial.sh",
            stdout=subprocess.PIPE,
            shell=True,
            cwd=self.workdir,
        )
        print("\nSetting up CMSSW and running CMSDriver:")
        print(process.communicate()[0])
        process.wait()

    def generate_gc_config(self):
        """
        automatically adapt a defaut gc config according to the paramters given by the user and by the request
        """
        if self.debug:
            print(f"Setting up GC config for {self.batch_system}")
        try:
            default_config = open(f"gc_configs/{self.batch_system}.conf", "r")
        except IOError:
            raise Exception(
                f"No default config for {self.batch_system} found in gc_configs"
            )
        f_config = open(
            f"{self.workdir}/gc_{self.label}_{self.batch_system}.conf", "w+"
        )
        f_config.write(default_config.read().format(**self.gc_parameters))
        if self.debug:
            print(
                f"Finished writing {self.workdir}/gc_{self.label}_{self.batch_system}.conf"
            )
        default_config.close()
        f_config.close()

    def modify_cmsRun_for_gc(self):
        """
        modify the config such that it works with grid control
        """
        for i, task in enumerate(self.tasks):
            print(f"Modifying {self.workdir}/{task}")
            configfile = open(f"{self.workdir}/{task}", "a+")
            if self.cpus_per_job > 1:
                helpers.appendMultiThreading(configfile, self.cpus_per_job)
            helpers.appendSeeds(configfile)
            if i == 0:
                helpers.appendGCSpecifics(configfile)

    def finalize(self):
        print(
            "----------------------------------------------\n"
            "      Finished Setup Successfully!     \n"
            "----------------------------------------------\n"
            "In order to run the pulled request locally do:\n"
            "----------------------------------------------\n"
            f"source {self.workdir}/{self.label}_working.sh\n"
            f"grid-control/go.py {self.workdir}/gc_{self.label}_{self.batch_system}.conf\n"
            "----------------------------------------------\n"
            "To create the filelists do:\n"
            "----------------------------------------------\n"
            f"grid-control/scripts/dataset_list_from_gc.py {self.workdir}/gc_{self.label}_{self.batch_system}.conf -o {self.workdir}/filelist.dbs"
        )
