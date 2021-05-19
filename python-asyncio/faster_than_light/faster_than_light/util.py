import os
import base64


def ensure_directory(d):
    d = os.path.abspath(os.path.expanduser(d))
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def find_module(module_dirs, module_name):

    # Find the module in module_dirs
    for d in module_dirs:
        module = os.path.join(d, f'{module_name}.py')
        if os.path.exists(module):
            break
        else:
            module = None

    return module


def encode_module(module_dirs, module_name):

    with open(find_module(module_dirs, module_name), 'rb') as f:
        return base64.b64encode(f.read()).decode()
