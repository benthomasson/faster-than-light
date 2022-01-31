

import os
from faster_than_light.util import find_module, read_module

HERE = os.path.dirname(os.path.abspath(__file__))


def test_missing_module():
    os.chdir(HERE)
    assert find_module(['modules'], 'no_such_module') is None
    assert find_module(['modules'], 'argtest') is not None


def test_read_module():
    os.chdir(HERE)

    assert read_module(['modules'], 'argtest') is not None
