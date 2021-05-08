
import yaml


def load_inventory(inventory_file):

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data
