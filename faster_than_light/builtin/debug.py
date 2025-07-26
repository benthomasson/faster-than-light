#!/usr/bin/python3

import json
import sys

args = sys.argv
with open(sys.argv[0]) as f:
    executable = f.read()
with open(sys.argv[1]) as f:
    more_args = f.read()

print(
    json.dumps(
        {
            "args": args,
            "more_args": more_args,
        }
    )
)
