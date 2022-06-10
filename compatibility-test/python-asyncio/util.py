

import os
import shutil
import subprocess


def find_galaxy():
    return shutil.which('ansible-galaxy')


def find_module(name):
    collection, _, module = name.rpartition('.')
    output = subprocess.check_output([find_galaxy(), 'collection', 'list', collection])
    locations = []
    for line in output.splitlines():
        line = line.decode()
        if line.startswith('# '):
            location = line[2:]
            if os.path.exists(location):
                locations.append(location)
    for location in locations:
        collection_parts = collection.split('.')
        collection_location = os.path.join(location, *collection_parts)
        if os.path.exists(collection_location):
            module_location = os.path.join(collection_location, 'plugins', 'modules', f"{module}.py")
            if os.path.exists(module_location):
                return module_location, os.path.dirname(module_location)
    return None



