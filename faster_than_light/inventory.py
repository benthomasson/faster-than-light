import sys
from typing import Any

import yaml


def load_inventory(inventory_file: str) -> Any:

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data


def load_localhost(interpreter=None) -> Any:

    if interpreter is None:
        interpreter = sys.executable

    inventory_data = {
        "all": {
            "hosts": {
                "localhost": {
                    "ansible_connection": "local",
                    "ansible_python_interpreter": interpreter,
                }
            }
        }
    }

    return inventory_data

def write_localhost(inventory_file: str = "inventory.yml") -> None:
    with open(inventory_file, "w") as f:
        yaml.dump(load_localhost(), stream=f)


def entry_point() -> None:
    write_localhost()
