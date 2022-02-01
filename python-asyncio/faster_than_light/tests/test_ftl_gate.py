

import asyncio
import os
import pytest
import base64
from pprint import pprint

from faster_than_light.message import read_message, send_message
from faster_than_light.gate import build_ftl_gate
from faster_than_light.module import run_module_on_host, find_module
from faster_than_light.util import clean_up_ftl_cache, clean_up_tmp

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.asyncio
async def test_read_message():
    os.chdir(HERE)
    ftl_gate = build_ftl_gate()
    proc = await asyncio.create_subprocess_shell(
        ftl_gate,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        proc.stdin.write(b'0000000d["Hello", {}]')
        message = await read_message(proc.stdout)
        assert message[0] == "Hello"
        assert message[1] == {}
    except Exception:
        print((await proc.stderr.read()).decode())
        raise
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)
        clean_up_ftl_cache()
        clean_up_tmp()

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
        clean_up_ftl_cache()
        clean_up_tmp()


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
        assert message[0] != "GateSystemError", message[1]
        assert message[0] == "ModuleResult"
        assert message[1] != {}
        assert message[1]['stdout']
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)
        clean_up_ftl_cache()
        clean_up_tmp()


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
        assert message[0] != "GateSystemError", message[1]
        assert message[0] == "FTLModuleResult"
        assert message[1] != {}
        assert message[1]['result']
    finally:
        send_message(proc.stdin, 'Shutdown', {})
        await proc.wait()
        os.unlink(ftl_gate)
        clean_up_tmp()
