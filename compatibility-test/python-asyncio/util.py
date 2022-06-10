

import os
import shutil
import subprocess


def find_galaxy():
    return shutil.which('ansible-galaxy')

def find_ansible():
    return shutil.which('ansible')


def find_builtin(name):
    output = subprocess.check_output([find_ansible(), '--version'])
    builtin, _, module = name.rpartition('.')
    assert builtin == 'ansible.builtin'
    for line in output.splitlines():
        line = line.decode()
        line = line.strip()
        if line.startswith('ansible python module location ='):
            print(line)
            _, _, ansible_location = line.partition('=')
            ansible_location = ansible_location.strip()
            print(ansible_location)
            module_location = os.path.join(ansible_location, 'modules', f"{module}.py")
            print(module_location)
            if os.path.exists(module_location):
                return module_location, os.path.dirname(module_location)

    return None, None

def find_module(name: str):
    if name.startswith('ansible.builtin'):
        return find_builtin(name)
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
    return None, None



