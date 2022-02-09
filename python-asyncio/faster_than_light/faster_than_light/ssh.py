

import os
import sys
import uuid
import base64
import asyncssh
import asyncssh.misc

from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess

from typing import Dict, Optional, Callable, cast, Tuple
from .types import Gate
from .message import send_message_str, read_message
from .util import process_module_result


async def connect_gate(
    gate_builder: Callable,
    ssh_host: str,
    gate_cache: Optional[Dict[str, Gate]],
    interpreter: str,
) -> Gate:
    while True:
        try:
            conn = await asyncssh.connect(ssh_host)
            await check_version(conn, interpreter)
            tempdir = f"/tmp/ftl-{uuid.uuid4()}"
            result = await conn.run(f"mkdir {tempdir}", check=True)
            result = await conn.run(
                f'touch {os.path.join(tempdir, "args")}', check=True
            )
            assert result.exit_status == 0
            await send_gate(gate_builder, conn, tempdir, interpreter)
            gate_process = await open_gate(conn, tempdir)
            return Gate(conn, gate_process, tempdir)
        except ConnectionResetError:
            print("retry connection")
            await remove_item_from_cache(gate_cache)
            continue
        except asyncssh.misc.ConnectionLost:
            print("retry connection")
            await remove_item_from_cache(gate_cache)
            continue


async def check_version(conn: SSHClientConnection, interpreter: str) -> None:
    result = await conn.run(f"{interpreter} --version")
    if result.stdout:
        output = cast(str, result.stdout)
        python_version = output.strip()
        for line in python_version.split("\n"):
            line = line.strip()
            if line.startswith("Python "):
                _, _, version = line.partition(" ")
                major, _, _ = version.split(".")
                if int(major) < 3:
                    raise Exception("Python 3 or greater required for interpreter")
            else:
                raise Exception(
                    f"Ensure that non-interactive shells emit no text: {line}"
                )


async def send_gate(
    gate_builder: Callable, conn: SSHClientConnection, tempdir: str, interpreter: str
) -> None:
    ftl_gate = gate_builder(interpreter=interpreter)
    async with conn.start_sftp_client() as sftp:
        await sftp.put(ftl_gate, f"{tempdir}/ftl_gate.pyz")
    result = await conn.run(f"chmod 700 {tempdir}/ftl_gate.pyz", check=True)
    assert result.exit_status == 0


async def open_gate(conn: SSHClientConnection, tempdir: str) -> SSHClientProcess:
    process = await conn.create_process(f"{tempdir}/ftl_gate.pyz")
    send_message_str(process.stdin, "Hello", {})
    assert await read_message(process.stdout) == ["Hello", {}]
    return process


async def remove_item_from_cache(gate_cache: Optional[Dict[str, Gate]]) -> None:
    if gate_cache is not None and gate_cache:
        item, (conn, gate_process, tempdir) = gate_cache.popitem()
        await close_gate(conn, gate_process, tempdir)
        print("closed gate", item)


async def close_gate(conn, gate_process, tempdir: str) -> None:

    try:
        if gate_process is not None:
            send_message_str(gate_process.stdin, "Shutdown", {})
        if gate_process is not None and gate_process.exit_status is not None:
            await gate_process.stderr.read()
    finally:
        conn.close()
    # result = await conn.run(f'rm -rf {tempdir}', check=True)
    # assert result.exit_status == 0


async def run_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Dict:
    with open(module, "rb") as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(
        gate_process.stdin,
        "Module",
        dict(module=module_text, module_name=module_name, module_args=module_args),
    )
    return process_module_result(await read_message(gate_process.stdout))


async def run_ftl_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Dict:
    with open(module, "rb") as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(
        gate_process.stdin,
        "FTLModule",
        dict(module=module_text, module_name=module_name, module_args=module_args),
    )
    return process_module_result(await read_message(gate_process.stdout))


async def run_module_remotely(
    host_name: str,
    host: Dict,
    module: str,
    module_args: Dict,
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder: Callable,
) -> Tuple[str, Dict]:
    module_name = os.path.basename(module)
    if host and host.get("ansible_host"):
        ssh_host = host.get("ansible_host")
    else:
        ssh_host = host_name
    if host and host.get("ansible_python_interpreter"):
        interpreter = host.get("ansible_python_interpreter")
    else:
        interpreter = sys.executable
    while True:
        try:
            if gate_cache is not None and gate_cache.get(host_name):
                conn, gate_process, tempdir = gate_cache[host_name]
                del gate_cache[host_name]
            else:
                conn, gate_process, tempdir = await connect_gate(
                    gate_builder, ssh_host, gate_cache, interpreter
                )
            try:
                return host_name, await remote_runner(
                    gate_process, module, module_name, module_args
                )
            finally:
                if gate_cache is None:
                    await close_gate(conn, gate_process, tempdir)
                else:
                    gate_cache[host_name] = Gate(conn, gate_process, tempdir)
            break
        except ConnectionResetError:
            print("retry connection")
            # Randomly close a connection in the cache
            await remove_item_from_cache(gate_cache)
            continue

    return host_name, None
