import request
import yaml
import argparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description="A small tool to setup a given McM request for local production")
parser.add_argument('--keys', help='keys of the configs you want to set up given in the config yaml file', nargs='+')
parser.add_argument('--config_file', help='yaml file with the configs for the jobs you want to run')
parser.add_argument('--debug', help='additional printouts', action='store_true')
args = parser.parse_args()

request_dict = yaml.load(open(args.config_file), Loader=yaml.Loader)

for key in args.keys:
    print("setting up {}".format(key))
    mc_request = request.McmRequest(request_dict[key], debug=args.debug)
    mc_request.setup_all()
