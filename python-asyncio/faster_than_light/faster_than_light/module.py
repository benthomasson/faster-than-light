
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
from .util import chunk


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


async def send_gate(conn, tempdir):
    ftl_gate = build_ftl_gate()
    async with conn.start_sftp_client() as sftp:
        await sftp.put(ftl_gate, f'{tempdir}/')
    result = await conn.run(f'chmod 700 {tempdir}/ftl_gate.pyz', check=True)
    assert result.exit_status == 0


async def open_gate(conn, tempdir):
    process = await conn.create_process(f'{tempdir}/ftl_gate.pyz')
    send_message_str(process.stdin, "Hello", {})
    assert await read_message(process.stdout) == ['Hello', {}]
    return process


async def run_module_through_gate(gate_process, module, module_name):
    with open(module, 'rb') as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(gate_process.stdin, 'Module', dict(module=module_text, module_name=module_name))
    return await read_message(gate_process.stdout)


async def run_ftl_module_through_gate(gate_process, module, module_name):
    with open(module, 'rb') as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(gate_process.stdin, 'FTLModule', dict(module=module_text, module_name=module_name))
    return await read_message(gate_process.stdout)


async def run_module_locally(host_name, host, module):
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


async def run_ftl_module_locally(host_name, host, module_path):

    with open(module_path, 'rb') as f:
        module_compiled = compile(f.read(), module_path, 'exec')

    globals = {'__file__': module_path}
    locals = {}

    exec(module_compiled, globals, locals)
    result = await locals['main']()
    return host_name, result


async def run_module_on_host(host_name, host, module, local_runner, remote_runner):
    if host and host.get('ansible_connection') == 'local':
        return await local_runner(host_name, host, module)
    else:
        module_name = os.path.basename(module)
        if host and host.get('ansible_host'):
            ssh_host = host.get('ansible_host')
        else:
            ssh_host = host_name
        while True:
            try:
                async with asyncssh.connect(ssh_host) as conn:
                    process = None
                    try:
                        tempdir = f'/tmp/ftl-{uuid.uuid4()}'
                        result = await conn.run(f'mkdir {tempdir}', check=True)
                        result = await conn.run(f'touch {os.path.join(tempdir, "args")}', check=True)
                        assert result.exit_status == 0
                        await send_gate(conn, tempdir)
                        gate_process = await open_gate(conn, tempdir)
                        return host_name, await remote_runner(gate_process, module, module_name)
                    finally:
                        if process is not None:
                            send_message_str(process.stdin, "Shutdown", {})
                        if process is not None and process.exit_status is not None:
                            # print(await process.stderr.read())
                            await process.stderr.read()
                        result = await conn.run(f'rm -rf {tempdir}', check=True)
                        assert result.exit_status == 0
                    # print(result.exit_status)
                break
            except ConnectionResetError:
                print('retry connection')
                await asyncio.sleep(1)
                continue

        return host_name, None


def unique_hosts(inventory):

    hosts = {}

    for group_name, group in inventory.items():
        for host_name, host in group.get('hosts').items():
            hosts[host_name] = host

    return hosts


def extract_task_results(tasks):

    results = {}
    for task in tasks:
        host_name, result = task.result()
        results[host_name] = result
    return results


async def _run_module(inventory, module_dirs, module_name, local_runner, remote_runner):

    module = find_module(module_dirs, module_name)

    if module is None:
        raise Exception('Module not found')

    hosts = unique_hosts(inventory)

    all_tasks = []
    # Run the tasks in chunks of 10 to reduce contention for remote connections.
    # This doubles performance at num_hosts=1000 for remote execution
    for c in chunk(list(hosts.items()), 10):
        tasks = []
        for host_name, host in c:
            tasks.append(asyncio.create_task(run_module_on_host(host_name, host, module, local_runner, remote_runner)))
        await asyncio.gather(*tasks)
        all_tasks.extend(tasks)

    return extract_task_results(all_tasks)


async def run_module(inventory, module_dirs, module_name):
    '''
    Runs a module on all items in an inventory concurrently.
    '''

    return await _run_module(inventory, module_dirs, module_name, run_module_locally, run_module_through_gate)


async def run_ftl_module(inventory, module_dirs, module_name):
    '''
    Runs a module on all items in an inventory concurrently.
    '''

    return await _run_module(inventory, module_dirs, module_name, run_ftl_module_locally, run_ftl_module_through_gate)
