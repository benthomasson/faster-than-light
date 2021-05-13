
import os
import sys
import tempfile
import zipapp
import shutil
from importlib_resources import files
import faster_than_light.ftl_gate

from .util import ensure_directory


def build_ftl_gate():

    cache = ensure_directory('~/.ftl')

    cached_gate = os.path.join(cache, 'ftl_gate.pyz')
    if os.path.exists(cached_gate):
        return cached_gate

    tempdir = tempfile.mkdtemp()
    os.mkdir(os.path.join(tempdir, 'ftl_gate'))
    with open(os.path.join(tempdir, 'ftl_gate', '__main__.py'), 'w') as f:
        f.write(files(faster_than_light.ftl_gate).joinpath('__main__.py').read_text())
    zipapp.create_archive(os.path.join(tempdir, 'ftl_gate'),
                          os.path.join(tempdir, 'ftl_gate.pyz'),
                          sys.executable)
    shutil.rmtree(os.path.join(tempdir, 'ftl_gate'))
    shutil.copy(os.path.join(tempdir, 'ftl_gate.pyz'), cached_gate)

    return cached_gate
