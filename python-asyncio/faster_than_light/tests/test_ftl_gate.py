

import asyncio
import json
import os
import pytest
import sys
import tempfile
import zipapp
import shutil
import base64

from .test_1 import find_module

HERE = os.path.dirname(os.path.abspath(__file__))


def send_message(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data]).encode()
    print('{:08x}'.format(len(message)).encode())
    print(message)
    writer.write('{:08x}'.format(len(message)).encode())
    writer.write(message)

async def read_message(reader):
    length = await reader.read(8)
    value = await reader.read(int(length, 16))
    return json.loads(value)

def build_ftl_gate():

    tempdir = tempfile.mkdtemp()
    shutil.copytree(os.path.join(HERE, 'ftl_gate'), os.path.join(tempdir, 'ftl_gate'))
    zipapp.create_archive(os.path.join(tempdir, 'ftl_gate'),
                          os.path.join(tempdir, 'ftl_gate.pyz'),
                          sys.executable)
    shutil.rmtree(os.path.join(tempdir, 'ftl_gate'))
    return os.path.join(tempdir, 'ftl_gate.pyz')


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
        send_message(proc.stdin, 'Module', dict(module=module))
        message = await read_message(proc.stdout)
        assert message[0] == "ModuleResult"
        assert message[1] != {}
        assert message[1]['stdout']
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)
