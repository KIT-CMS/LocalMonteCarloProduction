import os
import requests


def validate_config(dict):
    """
    check if all required paramters are given in
    the configuration before attempting to setup everything
    """
    required_keys = [
        "request_id",
        "label",
        "input_files",
        "workdir",
        "output_path",
        "batch_system",
        "total_events",
        "events_per_job",
    ]
    keys_with_defaults = ["cpus_per_job", "accounting_group", "scratch_space_used"]
    all_possible_keys = required_keys + keys_with_defaults
    # check if all given keys are valid
    for key in dict.keys():
        if key not in all_possible_keys:
            return False
    # check if all required keys are given
    if len(dict.keys()) < len(required_keys):
        return False
    return True


def createFolder(path):
    """
    Creates folder if not existent yet
    Return True if folder is created
    """
    if not os.path.isdir(path):
        # print("Creating: {}".format(path))
        os.makedirs(path)
        return True
    else:
        print("Using existent : {}".format(path))
        return False


def initiate_cmssw(workdir, version, arch, setupfile, initfile):
    """
    Sets up the desired CMSSW version for the selected arch in the given workdir
    """
    os.environ["SCRAM_ARCH"] = arch
    setupfile.write(
        f"export SCRAM_ARCH={arch}\n"
        "source /cvmfs/cms.cern.ch/cmsset_default.sh\n"
        "seed=$(($(date +%s) % 100 + 1))\n"
        f"cd {os.path.join(workdir)}\n"
        f"scram p {version}\n"
        f"cd {os.path.join(version)}/src\n"
        "eval `scram runtime -sh`\n"
    )

    initfile.write(
        f"source /cvmfs/cms.cern.ch/cmsset_default.sh\n"
        f"cd {os.path.join(workdir, version)}/src\n"
        "eval `scram runtime -sh`\n"
    )


def getFragment(id, fragment, fragmentPath):
    """
    grap a given fragment from mcm and placing it in the desired folder
    """
    createFolder(os.path.split(fragmentPath)[0])
    filename = os.path.join(fragmentPath)
    if not os.path.isfile(fragmentPath):
        print("Grabbing fragment from {}".format(fragment))
        r = requests.get(fragment, verify=False)
        open(filename, "wb").write(r.content)
    else:
        print("Using existent fragment")


def scram(path, setupfile, initfile):
    setupfile.write("scram b\n" "cd ../../\n")
    initfile.write(
        "cd ../../../../\n"
        "source /cvmfs/grid.cern.ch/umd-c7ui-latest/etc/profile.d/setup-c7-ui-example.sh\n"
    )


def check_machine(arch):
    """
    Check if the current machine is compatible with the arch of the request
    """


def updateDriverCommands(
    index, command, events_per_job, label, setupfile, cpus_per_job=1, debug=False
):
    """
    Update the cmsDriver command accordingly
    example command: 
    ```command
    cmsDriver.py Configuration/GenProduction/python/TAU-RunIIFall18wmLHEGS-00018-fragment.py \\
        --fileout file:TAU-RunIIFall18wmLHEGS-00018.root \\
        --mc --eventcontent RAWSIM,LHE \\
        --datatier GEN-SIM,LHE \\
        --conditions 102X_upgrade2018_realistic_v11 \\
        --beamspot Realistic25ns13TeVEarly2018Collision \\
        --step LHE,GEN,SIM \\
        --geometry DB:Extended \\
        --era Run2_2018 \\
        --python_filename TAU-RunIIFall18wmLHEGS-00018_1_cfg.py \\
        --no_exec \\
        --customise Configuration/DataProcessing/Utils.addMonitoring \\
        --customise_commands process.RandomNumberGeneratorService.externalLHEProducer.initialSeed="int(${seed})" \\
        -n 4348 || exit $? ;
    ```
    """
    filename = f"{label}_{index}_cfg.py"
    # parse the command splitted by spaces
    commandList = command.split(" ")
    for i, part in enumerate(commandList):
        if "--fileout" in part:
            commandList[i + 1] = f"file:{label}_{index}.root"
        if "--filein" in part and index > 0:
            commandList[i + 1] = f"file:{label}_{index-1}.root"
        if "--python_filename" in part:
            commandList[i + 1] = str(filename)
        if "$EVENTS" in part:
            commandList[i] = str(events_per_job)
        # This only works for CMMSSW_10_6_28 and above:
        # https://twiki.cern.ch/twiki/bin/view/CMSPublic/WorkBookGenMultithread
        # if "||" in part and cpus_per_job > 1:
        #     commandList[i] = f"--Threads {cpus_per_job} ||"
    setupfile.write(" ".join(commandList))
    setupfile.write("\n")
    if debug:
        print(f"Generated cmsDriver command for {filename}:\n\t{' '.join(commandList)}")
    return filename


def appendMultiThreading(configfile, cpus_per_job):
    """
    Add multi-threading to the given cmsRun config
    """
    configfile.write(
        f"process.options.numberOfThreads=cms.untracked.uint32({cpus_per_job})\n"
        "process.options.numberOfStreams=cms.untracked.uint32(0)\n"
    )


def appendSeeds(configfile):
    """
    Add random seeds to the given cmsRun config
    """
    configfile.write(
        "####@FILE_NAMES@, @SKIP_EVENTS@, @MAX_EVENTS@\n"
        "from IOMC.RandomEngine.RandomServiceHelper import RandomNumberServiceHelper\n"
        "randSvc = RandomNumberServiceHelper(process.RandomNumberGeneratorService)\n"
        "randSvc.populate()\n"
        'print("Generator random seed: %s" % process.RandomNumberGeneratorService.generator.initialSeed)\n'
    )


def appendGCSpecifics(configfile):
    """
    Add needed gc function to the given cmsRun config
    """
    f = open("gc_configs/customise_for_gc.py")
    for line in f.readlines():
        configfile.write(line)
    f.close()
