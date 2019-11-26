import request
import yaml
import argparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description="A small tool to setup a given McM request for local production")
parser.add_argument('--keys', help='keys given in request_config.yaml', nargs='+')
args = parser.parse_args()

request_dict = yaml.load(open("request_config.yaml"))

for key in args.keys:
    print("setting up {}".format(key))
    mc_request = request.McmRequest(request_dict[key])
    mc_request.setup_all()
