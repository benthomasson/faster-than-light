#!/usr/bin/python

import os
import sys
import json
import glob

args = sys.argv
with open(sys.argv[0]) as f:
    executable = f.read()
with open(sys.argv[1]) as f:
    more_args = f.read()
files = glob.glob(os.path.join(os.path.dirname(sys.argv[0]), '*'))
env = os.environ

print(json.dumps({
    "args" : args,
    "executable": executable,
    "more_args": more_args,
    "files": files,
    "env": dict(env)
}))


