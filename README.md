# LocalMonteCarloProduction
Script to automatically setup a local grid control task for a given McM request
## Usage

Setup a new workdir with 
```bash 
python main.py --keys example
```
`--keys` must contain a list of keys from `request_config.yaml`. In this configuration file, the parameters needed for the setup have to be specified.

```yaml
example:
  requestID : "HIG-RunIISummer16NanoAODv5-00031" # the string of the McM request
  label : "GluGluH_NanoAOD" # label used for personal bookkeeping
  inputFiles : "" # specified input files, either path to a filelist or a dbs entry
  workdir : "workdir_nano" # path to the desired workdir
  outputPath : "srm://cmssrm-kit.gridka.de:8443/srm/managerv2?SFN=/pnfs/gridka.de/cms/disk-only/store/user/sbrommer/gc_storage/private_mc_16" # path to the desired output location. This path should be given in correct grid control syntax
  batchSystem : "freiburg" # batch system option: currently available: freiburg
  totalEvents : 100000 # total number of events in the task. If an input file is speficied, the whole file will be processed instead
  eventsPerJob : 1000 # number of events per job
```
