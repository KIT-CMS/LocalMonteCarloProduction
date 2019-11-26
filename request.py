import requests
import os
import helpers
import subprocess


class McmRequest():
    RequestID = ""
    RequestConfig = {}

    def __init__(self, config_data):
        if not helpers.validate_config(config_data):
            raise Exception("Yaml config is not correct ! Pls fix")
        self.RequestID = config_data["requestID"]
        self.label = config_data["label"]
        self.workdir = os.path.abspath(config_data["workdir"])
        self.outputPath = config_data["outputPath"]
        self.batchSystem = config_data["batchSystem"]
        self.totalEvents = config_data["totalEvents"]
        self.InputFiles = config_data["inputFiles"]
        self.eventsPerJob = config_data["eventsPerJob"]
        self.tasks = []
        self.gc_parameters = {}

    def setup_all(self):
        """
            run all nessessay steps
        """
        self.get_request()
        self.setup_cmssw()
        self.generate_gc_config()
        self.modify_cmsRun_for_gc()
        self.finalize()

    def get_request(self):
        """
            get request from McM
        """
        url = "https://cms-pdmv.cern.ch/mcm/public/restapi/requests/get_setup/{request}".format(
            request=self.RequestID)
        print(url)
        setup = requests.get(url, verify=False)
        self.RequestConfig = parse_setup(setup.text)

    def setup_cmssw(self):
        """
            setup CMSSW workdir
        """
        print("Setting up Grid Control for {}".format(self.RequestID))
        print("generating source script {}.sh".format(self.label))
        helpers.createFolder(self.workdir)
        f_initial = open("{}/{}_initial.sh".format(self.workdir, self.label),
                         "w+")
        f_working = open("{}/{}_working.sh".format(self.workdir, self.label),
                         "w+")

        if helpers.createFolder(
                os.path.join(self.workdir, self.RequestConfig["cmssw"],
                             "src")):
            helpers.initiate_cmssw(self.workdir, self.RequestConfig["cmssw"],
                                   self.RequestConfig["arch"], f_initial,
                                   f_working)
        else:
            print("workdir is already setup")
        if self.RequestConfig['fragment'] is not "":
            helpers.getFragment(
                self.RequestID, self.RequestConfig['fragment'],
                os.path.join(self.workdir, self.RequestConfig["cmssw"], "src",
                             self.RequestConfig['fragmentPath']))
        helpers.scram(os.path.join(self.workdir, self.RequestConfig["cmssw"]),
                      f_initial, f_working)
        helpers.cloneGc(self.workdir, f_initial, f_working)
        for i, driver in enumerate(self.RequestConfig["driverCommand"]):
            self.tasks.append(
                helpers.updateDriverCommands(i, driver, self.eventsPerJob,
                                             self.label, self.workdir,
                                             f_initial))
        # construct dict for gc config file
        self.gc_parameters["workdir"] = self.workdir
        self.gc_parameters["jobs"] = str(
            int(self.totalEvents / self.eventsPerJob))
        self.gc_parameters["config file"] = " ".join(self.tasks)
        self.gc_parameters["events per job"] = str(self.eventsPerJob)
        self.gc_parameters["se output files"] = self.tasks[-1].replace(
            "_cfg.py", ".root")
        self.gc_parameters["se output pattern"] = self.label + "/"
        self.gc_parameters["se path"] = str(self.outputPath)
        # check if input file is a dbs link or a filelist
        self.gc_parameters["dataset"] = ""
        if self.InputFiles is not "":
            if os.path.isfile(self.InputFiles):
                self.gc_parameters["dataset"] = "{} : list:{}".format(
                    self.label, self.InputFiles)
            elif len(self.InputFiles.split("/")) == 4:
                self.gc_parameters["dataset"] = "{} : {}".format(
                    self.label, self.InputFiles)
            else:
                raise Exception("{} is not a valid Inputfile !".format(
                    self.InputFiles))
        f_initial.close()
        f_working.close()
        os.chmod("{}/{}_initial.sh".format(self.workdir, self.label), 0o744)
        # run the setup shell script
        process = subprocess.Popen("./{}_initial.sh".format(self.label),
                                   stdout=subprocess.PIPE,
                                   shell=True,
                                   cwd=self.workdir)
        print(process.communicate()[0])
        process.wait()

    def generate_gc_config(self):
        """
            automatically adapt a defaut gc config according to the paramters given by the user and by the request
        """
        print("Setting up GC config for {}".format(self.batchSystem))
        try:
            default_config = open(
                "gc_configs/{}.conf".format(self.batchSystem), "r")
        except IOError:
            raise Exception(
                "No default config for {} found in gc_configs".format(
                    self.batchSystem))
        f_config = open(
            "{workdir}/gc_{label}_{batch}.conf".format(workdir=self.workdir,
                                                       label=self.label,
                                                       batch=self.batchSystem),
            "w+")
        for line in default_config:
            if "__set__" not in line:
                f_config.write(line)
            elif "dataset" in line and self.gc_parameters["dataset"] is "":
                # in this case, no input files are needed and the option is not required in the config
                continue
            elif "jobs" in line and self.gc_parameters["dataset"] is not "":
                # in this case, the number of jobs is given by the size of the input file
                continue
            else:
                f_config.write(modify_config(line, self.gc_parameters))
        print("Finished writing {workdir}/gc_{label}_{batch}.conf".format(
            workdir=self.workdir, label=self.label, batch=self.batchSystem))
        default_config.close()
        f_config.close()

    def modify_cmsRun_for_gc(self):
        """
            modify the config such that it works with grid control
        """
        for i, task in enumerate(self.tasks):
            print("Modifying {workdir}/{filename}".format(workdir=self.workdir,
                                                          filename=task))
            configfile = open(
                "{workdir}/{filename}".format(workdir=self.workdir,
                                              filename=task), "a+")
            helpers.appendSeeds(configfile)
            if i == 0:
                helpers.appendGCSpecifics(configfile)

    def finalize(self):
        print("----------------------------------------------")
        print("      Finished Setup Successfully!     ")
        print("----------------------------------------------")
        print("In order to run the pulled request locally do:")
        print("----------------------------------------------")
        print("source {}/{}_working.sh".format(self.workdir, self.label))
        print("go.py {workdir}/gc_{label}_{batch}.conf".format(
            workdir=self.workdir, label=self.label, batch=self.batchSystem))


def modify_config(line, dict):
    """
        set given value in the line with the given parameter in the dict
    """
    for parameter in dict.keys():
        if parameter in line:
            return line.replace("__set__", dict[parameter])


def parse_setup(setup_file):
    """
        parse the McM request file
    """
    data = {"cmssw": "", "driverCommand": [], 'arch': "", "fragment": "", "fragmentPath": ""}
    for line in setup_file.split("\n"):
        if "ARCH" in line and data["arch"] == "":
            data["arch"] = [s for s in line.split("=") if "gcc" in s][0]
        if "scram" in line and data["cmssw"] == "":
            data["cmssw"] = [s for s in line.split(" ") if "CMSSW_" in s][0]
        if "get_fragment" in line:
            data["fragment"] = [s for s in line.split(" ") if "https" in s][0]
            data["fragmentPath"] = [
                s for s in line.split(" ") if "fragment.py" in s
            ][0]
        if "cmsDriver" in line:
            data["driverCommand"].append(line)
    return data
