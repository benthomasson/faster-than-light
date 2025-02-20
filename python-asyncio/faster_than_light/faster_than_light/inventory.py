
import yaml

from typing import Any


def load_inventory(inventory_file: str) -> Any:

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data

def load_localhost() -> Any:

    inventory_data = yaml.safe_load(
'''
all:
  hosts:
    localhost:
      ansible_connection: local
      ansible_python_interpreter: /Users/ben/venv/agents/bin/python3
''')

    return inventory_data
