

import asyncio
import json
import os
import pytest
import sys
import tempfile
import zipapp
import shutil
import base64
import asyncssh
from pprint import pprint

from .test_1 import find_module

HERE = os.path.dirname(os.path.abspath(__file__))


def send_message(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data]).encode()
    print('{:08x}'.format(len(message)).encode())
    print(message)
    writer.write('{:08x}'.format(len(message)).encode())
    writer.write(message)


def send_message_str(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data])
    print('{:08x}'.format(len(message)))
    print(message)
    writer.write('{:08x}'.format(len(message)))
    writer.write(message)


async def read_message(reader):
    while True:
        length = await reader.read(8)
        try:
            value = await reader.read(int(length, 16))
        except ValueError:
            print(f'length {length}')
            raise
        return json.loads(value)


def build_ftl_gate():

    tempdir = tempfile.mkdtemp()
    shutil.copytree(os.path.join(HERE, 'ftl_gate'), os.path.join(tempdir, 'ftl_gate'))
    zipapp.create_archive(os.path.join(tempdir, 'ftl_gate'),
                          os.path.join(tempdir, 'ftl_gate.pyz'),
                          sys.executable)
    shutil.rmtree(os.path.join(tempdir, 'ftl_gate'))
    return os.path.join(tempdir, 'ftl_gate.pyz')


async def run_module_on_host(host_name, host, module):
    if host and host.get('ansible_connection') == 'local':
        raise NotImplementedError()
    else:
        # Remote connection
        # TODO: Implement remote connection
        module_name = os.path.basename(module)
        async with asyncssh.connect(host_name) as conn:
            try:
                ftl_gate = build_ftl_gate()
                result = await conn.run('mkdir /tmp/ftl', check=True)
                print(result.exit_status)
                result = await conn.run('touch /tmp/ftl/args', check=True)
                print(result.exit_status)
                async with conn.start_sftp_client() as sftp:
                    await sftp.put(ftl_gate, '/tmp/ftl/')
                result = await conn.run('chmod 700 /tmp/ftl/ftl_gate.pyz', check=True)
                print(result.exit_status)
                process = await conn.create_process('/tmp/ftl/ftl_gate.pyz')
                send_message_str(process.stdin, "Hello", {})
                assert await read_message(process.stdout) == ['Hello', {}]
                with open(module, 'rb') as f:
                    module_text = base64.b64encode(f.read()).decode()
                send_message_str(process.stdin, 'Module', dict(module=module_text, module_name=module_name))
                return host_name, await read_message(process.stdout)
            finally:
                send_message_str(process.stdin, "Shutdown", {})
                if process.exit_status is not None:
                    print(await process.stderr.read())
                result = await conn.run('rm -rf /tmp/ftl', check=True)
                print(result.exit_status)
        return host_name, None


@pytest.mark.asyncio
async def test_build_ftl_gate():
    os.chdir(HERE)
    ftl_gate = build_ftl_gate()
    proc = await asyncio.create_subprocess_shell(
        ftl_gate,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        send_message(proc.stdin, 'Hello', {})
        message = await read_message(proc.stdout)
        assert message[0] == "Hello"
        assert message[1] == {}
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)


@pytest.mark.asyncio
async def test_run_module():
    os.chdir(HERE)
    ftl_gate = build_ftl_gate()
    proc = await asyncio.create_subprocess_shell(
        ftl_gate,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        send_message(proc.stdin, 'Hello', {})
        message = await read_message(proc.stdout)
        assert message[0] == "Hello"
        assert message[1] == {}

        with open(find_module(['modules'], 'argtest'), 'rb') as f:
            module = base64.b64encode(f.read()).decode()
        send_message(proc.stdin, 'Module', dict(module=module, module_name='argtest'))
        message = await read_message(proc.stdout)
        assert message[0] == "ModuleResult"
        assert message[1] != {}
        assert message[1]['stdout']
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)


@pytest.mark.asyncio
async def test_run_ftl_module():
    os.chdir(HERE)
    ftl_gate = build_ftl_gate()
    proc = await asyncio.create_subprocess_shell(
        ftl_gate,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        send_message(proc.stdin, 'Hello', {})
        message = await read_message(proc.stdout)
        assert message[0] == "Hello"
        assert message[1] == {}

        with open(find_module(['ftl_modules'], 'argtest'), 'rb') as f:
            module = base64.b64encode(f.read()).decode()
        send_message(proc.stdin, 'FTLModule', dict(module=module, module_name='argtest'))
        message = await read_message(proc.stdout)
        assert message[0] == "FTLModuleResult"
        assert message[1] != {}
        assert message[1]['result']
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)


@pytest.mark.asyncio
async def test_run_module_on_host():
    os.chdir(HERE)
    hostname, output = await run_module_on_host('localhost',
                                                dict(),
                                                os.path.join(HERE, 'modules', 'argtest.py'))
    pprint(output)
    assert hostname == 'localhost'
    assert output[0] == 'ModuleResult'
