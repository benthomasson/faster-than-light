

import os
import pytest
import asyncio
import tempfile
import shutil
import json
import yaml
from pprint import pprint

HERE = os.path.dirname(os.path.abspath(__file__))


def load_inventory(inventory_file):

    with open(inventory_file) as f:
        inventory_data = yaml.safe_load(f.read())
    return inventory_data


def find_module(module_dirs, module_name):

    # Find the module in module_dirs
    for d in module_dirs:
        module = os.path.join(d, f'{module_name}.py')
        if os.path.exists(module):
            break
        else:
            module = None

    return module


async def run_module_on_host(host_name, host, module):
    if host.get('ansible_connection') == 'local':
        tmp = tempfile.mkdtemp()
        tmp_module = os.path.join(tmp, 'module.py')
        shutil.copy(module, tmp_module)
        # TODO: replace hashbang with ansible_python_interpreter
        # TODO: add utf-8 encoding line
        args = os.path.join(tmp, 'args')
        with open(args, 'w') as f:
            f.write('some args')
        output = await check_output(f'{tmp_module} {args}')
        return host_name, json.loads(output)
    else:
        # Remote connection
        # TODO: Implement remote connection
        return host_name, None


async def run_module(inventory, module_dirs, module_name):

    '''
    Runs a module on all items in an inventory concurrently.
    '''

    module = find_module(module_dirs, module_name)

    if module is None:
        raise Exception('Module not found')

    hosts = dict()

    tasks = []

    # Make a set of unique hosts
    for group_name, group in inventory.items():
        for host_name, host in group.get('hosts').items():
            hosts[host_name] = host

    # Create a set of tasks to run concurrently
    for host_name, host in hosts.items():
        tasks.append(asyncio.create_task(run_module_on_host(host_name, host, module)))

    # Await all the tasks
    await asyncio.gather(*tasks)

    # Extract results
    results = {}
    for task in tasks:
        host_name, result = task.result()
        print(host_name)
        print(result)
        results[host_name] = result

    return results


async def check_output(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)

    stdout, stderr = await proc.communicate()
    return stdout


async def run_ftl_module_on_host(hostname, host, module_path):

    if host.get('ansible_connection') == 'local':
        with open(module_path, 'rb') as f:
            module_compiled = compile(f.read(), module_path, 'exec')

        globals = {'__file__': module_path}
        locals = {}

        exec(module_compiled, globals, locals)
        result = await locals['main']()
        return hostname, result
    else:
        # TODO: implement remote execution
        return hostname, None


@pytest.mark.asyncio
async def test_checkoutput():
    os.chdir(HERE)
    output = await check_output('ping')
    print(output)
    assert output


@pytest.mark.asyncio
async def test_run_module_timetest():
    os.chdir(HERE)
    output = await run_module(load_inventory('inventory.yml'), ['modules'], 'timetest')
    pprint(output)
    assert output['localhost']


@pytest.mark.asyncio
async def test_run_module_argtest():
    os.chdir(HERE)
    output = await run_module(load_inventory('inventory.yml'), ['modules'], 'argtest')
    pprint(output)
    assert output['localhost']


@pytest.mark.asyncio
async def test_run_ftl_module_on_host():
    os.chdir(HERE)
    hostname, output = await run_ftl_module_on_host('localhost', dict(ansible_connection='local'), os.path.join(HERE, 'ftl_modules', 'argtest.py'))
    pprint(output)
    assert hostname == 'localhost'
    assert output == {'args': (), 'kwargs': {}}
