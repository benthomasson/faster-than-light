import glob
import os
import shutil
import json

from typing import List, Union, Dict
from .message import GateMessage
from .exceptions import ModuleNotFound


def ensure_directory(d: str) -> str:
    d = os.path.abspath(os.path.expanduser(d))
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def chunk(lst: List, n: int):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def find_module(module_dirs: List[str], module_name: str) -> Union[str, None]:

    """
    Finds a module file path in the module_dirs with the name module_name.

    Returns a file path.
    """

    module = None

    # Find the module in module_dirs
    for d in module_dirs:
        module = os.path.join(d, f"{module_name}.py")
        if os.path.exists(module):
            break
        else:
            module = None

    # Look for binary module in module_dirs
    if module is None:
        for d in module_dirs:
            module = os.path.join(d, module_name)
            if os.path.exists(module):
                break
            else:
                module = None

    return module


def read_module(module_dirs: List[str], module_name: str) -> bytes:

    module = find_module(module_dirs, module_name)

    if module:
        with open(module, "rb") as f:
            return f.read()
    else:
        raise ModuleNotFound(f"Cannot find {module_name} in {module_dirs}")


def clean_up_ftl_cache() -> None:
    cache = os.path.abspath(os.path.expanduser("~/.ftl"))
    if os.path.exists(cache) and os.path.isdir(cache) and ".ftl" in cache:
        shutil.rmtree(cache)


def clean_up_tmp() -> None:
    for d in glob.glob("/tmp/ftl-*"):
        if os.path.exists(d) and os.path.isdir(d) and "tmp" in d and "ftl" in d:
            shutil.rmtree(d)


def process_module_result(message: GateMessage) -> Dict:
    msg_type = message[0]
    if msg_type == "ModuleResult":
        if message[1]["stdout"]:
            return json.loads(message[1]["stdout"])
        else:
            return dict(error=dict(message=message[1]["stderr"]))
    elif msg_type == "GateSystemError":
        return dict(error=dict(error_type=message[0], message=message[1]))
    else:
        raise Exception("Not supported")
