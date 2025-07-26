#!/usr/bin/python3

import glob
import json
import os
import sys

args = sys.argv
with open(sys.argv[0]) as f:
    executable = f.read()
with open(sys.argv[1]) as f:
    more_args = f.read()
files = glob.glob(os.path.join(os.path.dirname(sys.argv[0]), '*'))
env = dict(os.environ)

print(json.dumps({
    "args" : args,
    "executable": executable,
    "more_args": more_args,
    "files": files,
    "env": env
}))


