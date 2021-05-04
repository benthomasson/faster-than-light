

import os
import pytest
import asyncio
import tempfile
import shutil
import json
from pprint import pprint

HERE = os.path.dirname(os.path.abspath(__file__))


async def run_module(module_dirs, module_name):

    for d in module_dirs:
        module = os.path.join(d, f'{module_name}.py')
        if os.path.exists(module):
            break
        else:
            module = None

    if module is None:
        raise Exception('Module not found')

    tmp = tempfile.mkdtemp()
    tmp_module = os.path.join(tmp, 'module.py')
    shutil.copy(module, tmp_module)
    args = os.path.join(tmp, 'args')
    with open(args, 'w') as f:
        f.write('some args')
    output =  await check_output(f'{tmp_module} {args}')
    return json.loads(output)


async def check_output(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)

    stdout, stderr = await proc.communicate()
    return stdout


@pytest.mark.asyncio
async def test_1():
    os.chdir(HERE)
    output = await check_output('ping')
    print(output)
    assert output


@pytest.mark.asyncio
async def test_2():
    os.chdir(HERE)
    output = await run_module(['modules'], 'timetest')
    pprint(output)
    assert output


@pytest.mark.asyncio
async def test_3():
    os.chdir(HERE)
    output = await run_module(['modules'], 'argtest')
    pprint(output)
    assert output
