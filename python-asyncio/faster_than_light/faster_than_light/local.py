import asyncio
import json
import os
import shutil
import tempfile
import sys
import runpy
import logging

from typing import Dict, Tuple

logger = logging.getLogger('faster_than_light.local')


async def check_output(cmd: str, stdin=None) -> bytes:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    stdout, stderr = await proc.communicate(stdin)
    return stdout


def is_binary_module(module: str) -> bool:
    try:
        with open(module) as f:
            for line in f.readlines():
                pass
        return False
    except UnicodeDecodeError:
        return True


def is_new_style_module(module: str) -> bool:
    with open(module) as f:
        for line in f.readlines():
            if "AnsibleModule(" in line:
                return True

    return False


def is_want_json_module(module: str) -> bool:
    with open(module) as f:
        for line in f.readlines():
            if "WANT_JSON" in line:
                return True

    return False


async def run_module_locally(
    host_name: str, host: Dict, module: str, module_args: Dict
) -> Tuple[str, Dict]:
    logger.debug(f'run_module_locally {host_name=} {module=} ')
    tmp = tempfile.mkdtemp()
    tmp_module = os.path.join(tmp, "module.py")
    shutil.copy(module, tmp_module)
    # TODO: replace hashbang with ansible_python_interpreter
    # TODO: add utf-8 encoding line
    interpreter = host.get("ansible_python_interpreter", sys.executable)
    logger.debug(f"{interpreter}")
    if is_binary_module(module):
        args = os.path.join(tmp, "args")
        with open(args, "w") as f:
            f.write(json.dumps(module_args))
        output = await check_output(f"{tmp_module} {args}")
    elif is_new_style_module(module):
        output = await check_output(
            f"{interpreter} {tmp_module}",
            stdin=json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)).encode(),
        )
    elif is_want_json_module(module):
        args = os.path.join(tmp, "args")
        with open(args, "w") as f:
            f.write(json.dumps(module_args))
        output = await check_output(f"{interpreter} {tmp_module} {args}")
    else:
        args = os.path.join(tmp, "args")
        with open(args, "w") as f:
            if module_args is not None:
                f.write(" ".join(["=".join([k, v]) for k, v in module_args.items()]))
            else:
                f.write("")
        output = await check_output(f"{interpreter} {tmp_module} {args}")
    try:
        return host_name, json.loads(output)
    except Exception:
        print(output)
        return host_name, dict(error=output)


async def run_ftl_module_locally(
    host_name: str, host: Dict, module_path: str, module_args: Dict
) -> Tuple[str, dict]:

    if module_args is None:
        module_args = {}

    module = runpy.run_path(module_path)

    result = await module["main"](**module_args)
    return host_name, result
