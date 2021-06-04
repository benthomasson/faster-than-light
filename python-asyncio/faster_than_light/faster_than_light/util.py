import base64
import glob
import os
import shutil


def ensure_directory(d):
    d = os.path.abspath(os.path.expanduser(d))
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def find_module(module_dirs, module_name):

    '''
    Finds a module file path in the module_dirs with the name module_name.

    Returns a file path.
    '''

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


def read_module(module_dirs, module_name):

    with open(find_module(module_dirs, module_name), 'rb') as f:
        return f.read()


def clean_up_ftl_cache():
    cache = os.path.abspath(os.path.expanduser("~/.ftl"))
    if os.path.exists(cache) and os.path.isdir(cache) and ".ftl" in cache:
        shutil.rmtree(cache)


def clean_up_tmp():
    for d in glob.glob('/tmp/ftl-*'):
        if os.path.exists(d) and os.path.isdir(d) and 'tmp' in d and 'ftl' in d:
            shutil.rmtree(d)
