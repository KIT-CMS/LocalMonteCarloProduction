import os
import requests


def validate_config(dict):
    """
        check if all needed paramters are given in
        the configuration before attempting to setup everything
    """
    if len(dict.keys()) != 8:
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
    setupfile.write("export SCRAM_ARCH={} \n".format(arch))
    setupfile.write("source /cvmfs/cms.cern.ch/cmsset_default.sh \n")
    setupfile.write("seed=$(($(date +%s) % 100 + 1)) \n")
    setupfile.write("cd {workdir} \n".format(workdir=os.path.join(workdir)))
    setupfile.write("scram p {cmssw} \n".format(cmssw=version))
    setupfile.write("cd {cmssw}/src \n".format(cmssw=os.path.join(version)))
    setupfile.write("eval `scram runtime -sh` \n \n")

    initfile.write("source /cvmfs/cms.cern.ch/cmsset_default.sh \n")
    initfile.write(
        "cd {workdir}/src \n".format(workdir=os.path.join(workdir, version)))
    initfile.write("eval `scram runtime -sh` \n")


def getFragment(id, fragment, fragmentPath):
    """
        grap a given fragment from mcm and placing it in the desired folder
    """
    createFolder(os.path.split(fragmentPath)[0])
    filename = os.path.join(fragmentPath)
    if not os.path.isfile(fragmentPath):
        print("Grabbing fragment from {}".format(fragment))
        r = requests.get(fragment, verify=False)
        open(filename, 'wb').write(r.content)
    else:
        print("Using existent fragment")


def scram(path, setupfile, initfile):
    setupfile.write("scram b \n")
    setupfile.write("cd ../../ \n")
    initfile.write("cd ../../ \n")


def cloneGc(path, setupfile, initfile):
    if not os.path.isdir(os.path.join(path, 'grid-control')):
        setupfile.write("git clone https://github.com/KIT-CMS/grid-control \n")
    setupfile.write("export PATH=$PATH:{}/grid-control \n".format(
        os.path.abspath(path)))
    setupfile.write("export PATH=$PATH:{}/grid-control/scripts \n \n".format(
        os.path.abspath(path)))
    initfile.write("export PATH=$PATH:{}/grid-control \n".format(
        os.path.abspath(path)))
    initfile.write("export PATH=$PATH:{}/grid-control/scripts \n".format(
        os.path.abspath(path)))


def check_machine(arch):
    """
        Check if the current machine is compatible with the arch of the request
    """


def updateDriverCommands(index, command, eventsPerJob, label, workdir,
                         setupfile):
    """
        Update the cmsDriver command accordingly
        example command: cmsDriver.py Configuration/GenProduction/python/TAU-RunIIFall18wmLHEGS-00018-fragment.py --fileout file:TAU-RunIIFall18wmLHEGS-00018.root --mc --eventcontent RAWSIM,LHE --datatier GEN-SIM,LHE --conditions 102X_upgrade2018_realistic_v11 --beamspot Realistic25ns13TeVEarly2018Collision --step LHE,GEN,SIM --geometry DB:Extended --era Run2_2018 --python_filename TAU-RunIIFall18wmLHEGS-00018_1_cfg.py --no_exec --customise Configuration/DataProcessing/Utils.addMonitoring --customise_commands process.RandomNumberGeneratorService.externalLHEProducer.initialSeed="int(${seed})" -n 4348 || exit $? ;
    """
    filename = 'asdf'
    # parse the command splitted by spaces
    commandList = command.split(" ")
    for i, part in enumerate(commandList):
        if "--fileout" in part:
            commandList[i + 1] = "file:{label}_{index}.root".format(
                label=label, index=index)
        if "--filein" in part and index > 0:
            commandList[i + 1] = "file:{label}_{index}.root".format(
                label=label, index=index - 1)
        if "--python_filename" in part:
            filename = "{label}_{index}_cfg.py".format(label=label,
                                                       index=index)
            commandList[i + 1] = "{filename}".format(filename=filename)
        if "-n " in part:
            commandList[i + 1] = "{}".format(eventsPerJob)
    setupfile.write(" ".join(commandList))
    setupfile.write("\n")
    print("Generated cmsDriver command for {}".format(filename))
    return filename


def appendSeeds(configfile):
    """
        Add random seeds to the given cmsRun config
    """
    configfile.write('''
####@FILE_NAMES@, @SKIP_EVENTS@, @MAX_EVENTS@
from IOMC.RandomEngine.RandomServiceHelper import RandomNumberServiceHelper
randSvc = RandomNumberServiceHelper(process.RandomNumberGeneratorService)
randSvc.populate()
print("Generator random seed: %s" % process.RandomNumberGeneratorService.generator.initialSeed)

''')


def appendGCSpecifics(configfile):
    """
        Add needed gc function to the given cmsRun config
    """
    f = open('gc_configs/customise_for_gc.py')
    for line in f.readlines():
        configfile.write(line)
    f.close()
