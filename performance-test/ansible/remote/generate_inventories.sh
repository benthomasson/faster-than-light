PYTHON_INTERPRETER=/usr/bin/python3
../../scripts/generate_inventory.py --python=$PYTHON_INTERPRETER 10000 > inventory_remote10000.yml
../../scripts/generate_inventory.py --python=$PYTHON_INTERPRETER 1000 > inventory_remote1000.yml
../../scripts/generate_inventory.py --python=$PYTHON_INTERPRETER 100 > inventory_remote100.yml
../../scripts/generate_inventory.py --python=$PYTHON_INTERPRETER 10 > inventory_remote10.yml
../../scripts/generate_inventory.py --python=$PYTHON_INTERPRETER 1 > inventory_remote1.yml
