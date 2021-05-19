
import hashlib
import os
import sys
import shutil
import tempfile
import zipapp

from importlib_resources import files
import faster_than_light.ftl_gate
from subprocess import check_output

from .util import ensure_directory, encode_module


def build_ftl_gate(modules=None, module_dirs=None, dependencies=None):

    cache = ensure_directory('~/.ftl')

    if modules is None:
        modules = []
    if module_dirs is None:
        module_dirs = []
    if dependencies is None:
        dependencies = []

    input_tuples = tuple([tuple(modules),
                         tuple(module_dirs),
                         tuple(dependencies)])

    inputs = []
    inputs.extend(modules)
    inputs.extend(module_dirs)
    inputs.extend(dependencies)

    gate_hash = hashlib.sha256("".join(inputs).encode()).hexdigest()

    cached_gate = os.path.join(cache, f'ftl_gate_{gate_hash}.pyz')
    if os.path.exists(cached_gate):
        return cached_gate

    tempdir = tempfile.mkdtemp()
    os.mkdir(os.path.join(tempdir, 'ftl_gate'))
    with open(os.path.join(tempdir, 'ftl_gate', '__main__.py'), 'w') as f:
        f.write(files(faster_than_light.ftl_gate).joinpath('__main__.py').read_text())

    # Install modules
    if modules:
        module_dir = os.path.join(tempdir, "modules")
        for module in modules:
            with open(os.path.join(module_dir, module), 'w') as f:
                f.write(encode_module(module_dirs))

    # Install dependencies for Gate
    if dependencies:
        requirements = os.path.join(tempdir, 'requirements.txt')
        with open(requirements, 'w') as f:
            f.write("\n".join(dependencies))
        output = check_output([sys.executable, '-m', 'pip', 'install', '-r', requirements, '--target', tempdir])
        print(output)

    zipapp.create_archive(os.path.join(tempdir, 'ftl_gate'),
                          os.path.join(tempdir, 'ftl_gate.pyz'),
                          sys.executable)
    shutil.rmtree(os.path.join(tempdir, 'ftl_gate'))
    shutil.copy(os.path.join(tempdir, 'ftl_gate.pyz'), cached_gate)

    return cached_gate
