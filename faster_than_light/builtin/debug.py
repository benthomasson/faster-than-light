#!/usr/bin/python3

import os
import sys
import json
import glob

args = sys.argv
with open(sys.argv[0]) as f:
    executable = f.read()
with open(sys.argv[1]) as f:
    more_args = f.read()

print(json.dumps({
    "args" : args,
    "more_args": more_args,
}))


