#!/usr/bin/python3


# AnsibleModule(

import os
import sys
import json
import glob

args = sys.argv
with open(sys.argv[0]) as f:
    executable = f.read()
files = glob.glob(os.path.join(os.path.dirname(sys.argv[0]), '*'))

print(json.dumps({
    "args" : args,
    "executable": executable,
    "files": files
}))


