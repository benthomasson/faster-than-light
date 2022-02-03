import asyncio
import asyncssh
import asyncssh.misc
import base64
import json
import os
import io
import sys
import shutil
import tempfile
import uuid
from functools import partial

from .message import send_message_str, read_message, GateMessage
from .gate import build_ftl_gate
from .util import chunk, find_module
from .types import Gate

from typing import Dict, Optional, Callable, cast, Tuple, List
from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess
from asyncio.tasks import Task


async def check_output(cmd: str, stdin=None) -> bytes:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    stdout, stderr = await proc.communicate(stdin)
    return stdout


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


def process_module_result(message: GateMessage) -> Dict:
    msg_type = message[0]
    if msg_type == "ModuleResult":
        if message[1]["stdout"]:
            return json.loads(message[1]["stdout"])
        else:
            return dict(error=dict(message=message[1]["stderr"]))
    elif msg_type == "GateSystemError":
        return dict(error=dict(error_type=message[0], message=message[1]))
    else:
        raise Exception("Not supported")


async def run_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Dict:
    # with open(module, 'rb') as f:
    #    module_text = base64.b64encode(f.read()).decode()
    module_text = None
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
    tmp = tempfile.mkdtemp()
    tmp_module = os.path.join(tmp, "module.py")
    shutil.copy(module, tmp_module)
    # TODO: replace hashbang with ansible_python_interpreter
    # TODO: add utf-8 encoding line
    interpreter = host.get("ansible_python_interpreter", "/usr/bin/python")
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

    with open(module_path, "rb") as f:
        module_compiled = compile(f.read(), module_path, "exec")

    globals = {"__file__": module_path}
    locals: Dict = {}

    exec(module_compiled, globals, locals)
    result = await locals["main"]()
    return host_name, result


async def remove_item_from_cache(gate_cache: Optional[Dict[str, Gate]]) -> None:
    if gate_cache is not None and gate_cache:
        item, (conn, gate_process, tempdir) = gate_cache.popitem()
        await close_gate(conn, gate_process, tempdir)
        print("closed gate", item)


async def connect_gate(
    gate_builder: Callable, ssh_host: str, gate_cache: Optional[Dict[str, Gate]], interpreter: str
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


async def run_module_on_host(
    host_name,
    host,
    module,
    module_args,
    local_runner,
    remote_runner,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder,
) -> Tuple[str, Dict]:
    if host and host.get("ansible_connection") == "local":
        return await local_runner(host_name, host, module, module_args)
    else:
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


def unique_hosts(inventory: Dict) -> Dict:

    hosts = {}

    for group_name, group in inventory.items():
        for host_name, host in group.get("hosts").items():
            hosts[host_name] = host

    return hosts


def extract_task_results(tasks: List[Task]) -> Dict[str, Dict]:

    results = {}
    for task in tasks:
        host_name, result = task.result()
        results[host_name] = result
    return results


async def _run_module(
    inventory: Dict,
    module_dirs: List[str],
    module_name: str,
    local_runner: Callable,
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    modules: Optional[List[str]],
    dependencies: Optional[List[str]],
    module_args: Optional[Dict],
) -> Dict[str, Dict]:

    module = find_module(module_dirs, module_name)

    if modules is None:
        modules = []
    if module_name not in modules:
        modules.append(module_name)

    if module is None:
        raise Exception(f"Module {module_name} not found in {module_dirs}")

    hosts = unique_hosts(inventory)

    gate_builder: Callable[[str], str] = partial(
        build_ftl_gate,
        modules=modules,
        module_dirs=module_dirs,
        dependencies=dependencies,
    )

    all_tasks = []
    # Run the tasks in chunks of 10 to reduce contention for remote connections.
    # This doubles performance at num_hosts=1000 for remote execution
    for c in chunk(list(hosts.items()), 10):
        tasks = []
        for host_name, host in c:
            tasks.append(
                asyncio.create_task(
                    run_module_on_host(
                        host_name,
                        host,
                        module,
                        module_args,
                        local_runner,
                        remote_runner,
                        gate_cache,
                        gate_builder,
                    )
                )
            )
        await asyncio.gather(*tasks)
        all_tasks.extend(tasks)

    return extract_task_results(all_tasks)


async def run_module(
    inventory: Dict,
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict] = None,
) -> Dict[str, Dict]:
    """
    Runs a module on all items in an inventory concurrently.
    """

    return await _run_module(
        inventory,
        module_dirs,
        module_name,
        run_module_locally,
        run_module_through_gate,
        gate_cache,
        modules,
        dependencies,
        module_args,
    )


async def run_ftl_module(
    inventory: Dict,
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict] = None,
) -> Dict[str, Dict]:
    """
    Runs a module on all items in an inventory concurrently.
    """

    return await _run_module(
        inventory,
        module_dirs,
        module_name,
        run_ftl_module_locally,
        run_ftl_module_through_gate,
        gate_cache,
        modules,
        dependencies,
        module_args,
    )
