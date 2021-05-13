
import asyncio
import asyncssh
import base64
import json
import os
import shutil
import tempfile
import uuid

from .message import send_message_str, read_message
from .gate import build_ftl_gate


async def check_output(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT)

    stdout, stderr = await proc.communicate()
    return stdout


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
    if host and host.get('ansible_connection') == 'local':
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
        module_name = os.path.basename(module)
        if host.get('ansible_host'):
            ssh_host = host.get('ansible_host')
        else:
            ssh_host = host_name
        while True:
            try:
                async with asyncssh.connect(ssh_host) as conn:
                    process = None
                    try:
                        tempdir = f'/tmp/ftl-{uuid.uuid4()}'
                        ftl_gate = build_ftl_gate()
                        result = await conn.run(f'mkdir {tempdir}', check=True)
                        #print(result.exit_status)
                        result = await conn.run(f'touch {os.path.join(tempdir, "args")}', check=True)
                        #print(result.exit_status)
                        async with conn.start_sftp_client() as sftp:
                            await sftp.put(ftl_gate, f'{tempdir}/')
                        result = await conn.run(f'chmod 700 {tempdir}/ftl_gate.pyz', check=True)
                        #print(result.exit_status)
                        process = await conn.create_process(f'{tempdir}/ftl_gate.pyz')
                        send_message_str(process.stdin, "Hello", {})
                        assert await read_message(process.stdout) == ['Hello', {}]
                        with open(module, 'rb') as f:
                            module_text = base64.b64encode(f.read()).decode()
                        send_message_str(process.stdin, 'Module', dict(module=module_text, module_name=module_name))
                        return host_name, await read_message(process.stdout)
                    finally:
                        if process is not None:
                            send_message_str(process.stdin, "Shutdown", {})
                        if process is not None and process.exit_status is not None:
                            #print(await process.stderr.read())
                            await process.stderr.read()
                        result = await conn.run(f'rm -rf {tempdir}', check=True)
                    #print(result.exit_status)
                break
            except ConnectionResetError:
                await asyncio.sleep(1)
                continue

        return host_name, None


async def run_module(inventory, module_dirs, module_name):

    '''
    Runs a module on all items in an inventory concurrently.
    '''

    module = find_module(module_dirs, module_name)

    if module is None:
        raise Exception('Module not found')

    # Make a set of unique hosts

    hosts = unique_hosts(inventory)

    # Create a set of tasks to run concurrently
    tasks = []
    for host_name, host in hosts.items():
        tasks.append(asyncio.create_task(run_module_on_host(host_name, host, module)))

    # Await all the tasks
    await asyncio.gather(*tasks)

    return extract_task_results(tasks)


async def run_ftl_module(inventory, module_dirs, module_name):

    '''
    Runs a module on all items in an inventory concurrently.
    '''

    module = find_module(module_dirs, module_name)

    if module is None:
        raise Exception('Module not found')

    # Make a set of unique hosts

    hosts = unique_hosts(inventory)

    # Create a set of tasks to run concurrently
    tasks = []
    for host_name, host in hosts.items():
        tasks.append(asyncio.create_task(run_ftl_module_on_host(host_name, host, module)))

    # Await all the tasks
    await asyncio.gather(*tasks)

    return extract_task_results(tasks)


def unique_hosts(inventory):

    hosts = {}

    for group_name, group in inventory.items():
        for host_name, host in group.get('hosts').items():
            hosts[host_name] = host

    return hosts


def extract_task_results(tasks):

    # Extract results
    results = {}
    for task in tasks:
        host_name, result = task.result()
        #print(host_name)
        #print(result)
        results[host_name] = result
    return results


async def run_ftl_module_on_host(hostname, host, module_path):

    if host and host.get('ansible_connection') == 'local':
        with open(module_path, 'rb') as f:
            module_compiled = compile(f.read(), module_path, 'exec')

        globals = {'__file__': module_path}
        locals = {}

        exec(module_compiled, globals, locals)
        result = await locals['main']()
        return hostname, result
    else:
        # TODO: implement remote execution
        raise NotImplementedError("implement remote execution for ftl modules")
        return hostname, None
