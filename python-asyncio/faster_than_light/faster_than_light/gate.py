
import os
import sys
import tempfile
import zipapp
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def build_ftl_gate():

    tempdir = tempfile.mkdtemp()
    shutil.copytree(os.path.join(HERE, 'ftl_gate'), os.path.join(tempdir, 'ftl_gate'))
    zipapp.create_archive(os.path.join(tempdir, 'ftl_gate'),
                          os.path.join(tempdir, 'ftl_gate.pyz'),
                          sys.executable)
    shutil.rmtree(os.path.join(tempdir, 'ftl_gate'))
    return os.path.join(tempdir, 'ftl_gate.pyz')
