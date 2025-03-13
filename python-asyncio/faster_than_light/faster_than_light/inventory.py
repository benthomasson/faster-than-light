
import yaml

from typing import Any


def load_inventory(inventory_file: str) -> Any:

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data

def load_localhost(interpreter="/usr/bin/python3") -> Any:

    inventory_data = {'all': {'hosts': {'localhost': {'ansible_connection': 'local', 'ansible_python_interpreter': interpreter}}}}

    return inventory_data
