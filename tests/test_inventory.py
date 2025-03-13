

from faster_than_light.inventory import load_inventory
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def test_inventory():
    os.chdir(HERE)
    inventory = load_inventory('inventory.yml')
    assert inventory
