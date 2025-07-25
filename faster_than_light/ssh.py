import os
import sys
import base64
import asyncssh
import asyncssh.misc
import asyncio
from getpass import getuser
import logging
import jinja2
import tempfile

from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess

from typing import Dict, Optional, Callable, cast, Tuple
from .types import Gate
from .message import send_message_str, read_message
from .util import process_module_result, unique_hosts
from .exceptions import ModuleNotFound

logger = logging.getLogger("faster_than_light.ssh")


async def connect_gate(
    gate_builder: Callable,
    ssh_host: str,
    ssh_port: str,
    ssh_user: str,
    gate_cache: Optional[Dict[str, Gate]],
    interpreter: str,
) -> Gate:
    logger.info(f"connect_gate {ssh_host=} {ssh_port=} {ssh_user=} {interpreter=}")
    while True:
        try:
            conn = await asyncssh.connect(
                ssh_host,
                port=ssh_port,
                username=ssh_user,
                known_hosts=None,
                connect_timeout="1h",
            )
            await check_version(conn, interpreter)
            tempdir = "/tmp"
            gate_file_name = await send_gate(gate_builder, conn, tempdir, interpreter)
            gate_process = await open_gate(conn, gate_file_name)
            return Gate(conn, gate_process, tempdir)
        except (ConnectionRefusedError, ConnectionResetError, asyncssh.misc.ConnectionLost, TimeoutError) as e:
            logger.info(f"retry connection, {type(e).__name__}")
            await remove_item_from_cache(gate_cache)
            continue
        except BaseException as e:
            logger.error(f"{type(e)}, {e}")
            raise


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


async def connect_ssh(host):

    ssh_host = host.get("ansible_host")
    if host and host.get("ansible_port"):
        ssh_port = host.get("ansible_port")
    else:
        ssh_port = 22

    if host and host.get("ansible_user"):
        ssh_user = host.get("ansible_user")
    else:
        ssh_user = getuser()

    conn = await asyncssh.connect(
        ssh_host,
        port=ssh_port,
        username=ssh_user,
        known_hosts=None,
        connect_timeout="1h",
    )

    return conn


async def mkdir(inventory, gate_cache, name: str) -> None:

    hosts = unique_hosts(inventory)

    for host in hosts:

        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn
        else:
            conn = await connect_ssh(hosts[host])

        async with conn.start_sftp_client() as sftp:
            await sftp.makedirs(name, exist_ok=True)


def mkdir_sync(inventory, gate_cache, name: str, loop=None) -> None:

    coro = mkdir(inventory, gate_cache, name)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def copy(inventory, gate_cache, src: str, dest: str) -> None:

    hosts = unique_hosts(inventory)

    results = {}

    for host in hosts:

        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn
        else:
            conn = await connect_ssh(hosts[host])
        async with conn.start_sftp_client() as sftp:
            await sftp.put(src, dest, recurse=True)

        results[host] = {"changed": True}

    return results


def copy_sync(inventory, gate_cache, src: str, dest: str, loop=None) -> None:

    coro = copy(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def template(inventory, gate_cache, src: str, dest: str) -> None:

    hosts = unique_hosts(inventory)

    results = {}

    environment = jinja2.Environment()

    for host_name, host in hosts.items():

        if gate_cache and host_name in gate_cache:
            gate = gate_cache.get(host_name)
            conn = gate.conn
        else:
            conn = await connect_ssh(host)

        tf, tf_path = tempfile.mkstemp()
        try:
            with open(src) as f:
                template = environment.from_string(f.read())
                os.write(tf, template.render(**host).encode())
                os.close(tf)

                async with conn.start_sftp_client() as sftp:
                    await sftp.put(tf_path, dest, recurse=True)
        finally:
            os.unlink(tf_path)

        results[host_name] = {"changed": True}

    return results


def template_sync(inventory, gate_cache, src: str, dest: str, loop=None) -> None:

    coro = template(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def copy_from(inventory, gate_cache, src: str, dest: str) -> None:

    hosts = unique_hosts(inventory)

    for host in hosts:

        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn
        else:
            conn = await connect_ssh(hosts[host])
        async with conn.start_sftp_client() as sftp:
            print(f"Copy from {src} to {dest}")
            await sftp.get(src, dest, recurse=True)


def copy_from_sync(inventory, gate_cache, src: str, dest: str, loop=None) -> None:

    coro = copy_from(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def send_gate(
    gate_builder: Callable, conn: SSHClientConnection, tempdir: str, interpreter: str
) -> None:
    ftl_gate, gate_hash = gate_builder(interpreter=interpreter)
    gate_file_name = os.path.join(tempdir, f"ftl_gate_{gate_hash}.pyz")
    async with conn.start_sftp_client() as sftp:
        if not await sftp.exists(gate_file_name):
            logger.info(f"send_gate sending {gate_file_name}")
            await sftp.put(ftl_gate, gate_file_name)
            result = await conn.run(f"chmod 700 {gate_file_name}", check=True)
            assert result.exit_status == 0
        else:
            stats = await sftp.lstat(gate_file_name)
            if stats.size == 0:
                logger.info(f"send_gate resending {gate_file_name}")
                await sftp.put(ftl_gate, gate_file_name)
                result = await conn.run(f"chmod 700 {gate_file_name}", check=True)
                assert result.exit_status == 0
            else:
                logger.info(f"send_gate reusing {gate_file_name}")
    return gate_file_name


async def open_gate(conn: SSHClientConnection, gate_file_name: str) -> SSHClientProcess:
    process = await conn.create_process(gate_file_name)
    send_message_str(process.stdin, "Hello", {})
    if await read_message(process.stdout) != ["Hello", {}]:
        error = await process.stderr.read()
        logger.error(error)
        raise Exception(error)
    return process


async def remove_item_from_cache(gate_cache: Optional[Dict[str, Gate]]) -> None:
    if gate_cache is not None and gate_cache:
        item, (conn, gate_process, tempdir) = gate_cache.popitem()
        await close_gate(conn, gate_process, tempdir)
        logger.info("closed gate", item)


async def close_gate(conn, gate_process, tempdir: str) -> None:

    try:
        if gate_process is not None:
            send_message_str(gate_process.stdin, "Shutdown", {})
        if gate_process is not None and gate_process.exit_status is not None:
            await gate_process.stderr.read()
    finally:
        conn.close()


async def run_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Dict:
    try:
        send_message_str(
            gate_process.stdin,
            "Module",
            dict(module_name=module_name, module_args=module_args),
        )
        return process_module_result(await read_message(gate_process.stdout))
    except ModuleNotFound:
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
    if host and host.get("ansible_port"):
        ssh_port = host.get("ansible_port")
    else:
        ssh_port = 22
    if host and host.get("ansible_user"):
        ssh_user = host.get("ansible_user")
    else:
        ssh_user = getuser()
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
                    gate_builder, ssh_host, ssh_port, ssh_user, gate_cache, interpreter
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
            logger.info("retry connection")
            # Randomly close a connection in the cache
            await remove_item_from_cache(gate_cache)
            continue

    return host_name, None
