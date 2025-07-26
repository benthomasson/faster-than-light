"""SSH operations and remote execution functionality for FTL.

This module provides comprehensive SSH connection management, file operations,
and remote module execution capabilities. It implements FTL's gate mechanism
for efficient remote automation tasks with connection caching, error handling,
and retry logic.

Key Features:
- SSH connection management with authentication
- Gate-based remote execution for scalability
- File operations (copy, template, mkdir) across inventories
- Connection caching for performance optimization
- Retry logic for network resilience
- Both async and sync APIs for flexibility
"""

import asyncio
import base64
import logging
import os
import sys
import tempfile
from getpass import getuser
from typing import Any, Callable, Dict, Optional, Tuple, cast

import asyncssh
import asyncssh.misc
import jinja2
from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess

from .exceptions import ModuleNotFound
from .message import GateMessage, read_message, send_message_str
from .types import Gate
from .util import process_module_result, unique_hosts

logger = logging.getLogger("faster_than_light.ssh")


async def connect_gate(
    gate_builder: Callable,
    ssh_host: str,
    ssh_port: int,
    ssh_user: str,
    gate_cache: Optional[Dict[str, Gate]],
    interpreter: str,
) -> Gate:
    """Establish an SSH connection and create a remote execution gate.

    Creates a persistent SSH connection to a remote host, verifies the Python
    interpreter, deploys the FTL gate executable, and starts the gate process
    for module execution. Includes retry logic for transient network issues.

    Args:
        gate_builder: Callable that creates the gate executable and returns
            (gate_path, gate_hash) tuple.
        ssh_host: Target hostname or IP address for SSH connection.
        ssh_port: SSH port number (typically 22).
        ssh_user: Username for SSH authentication.
        gate_cache: Optional cache for managing gate connections. Used for
            cleanup when connections fail.
        interpreter: Path to Python interpreter on remote host.

    Returns:
        Gate object containing the SSH connection, gate process, and temp directory.

    Raises:
        ConnectionRefusedError: SSH connection refused (retries automatically).
        ConnectionResetError: SSH connection reset (retries automatically).
        asyncssh.misc.ConnectionLost: SSH connection lost (retries automatically).
        TimeoutError: Connection timeout (retries automatically).
        Exception: Python version check failure or other non-retryable errors.

    Example:
        >>> gate = await connect_gate(
        ...     build_ftl_gate, "example.com", "22", "user", {}, "/usr/bin/python3"
        ... )
        >>> # Use gate for module execution
        >>> await close_gate(gate.conn, gate.gate_process, gate.temp_dir)

    Note:
        This function automatically retries on connection failures and manages
        gate cache cleanup. The returned Gate should be properly closed after use.
    """
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
        except (
            ConnectionRefusedError,
            ConnectionResetError,
            asyncssh.misc.ConnectionLost,
            TimeoutError,
        ) as e:
            logger.info(f"retry connection, {type(e).__name__}")
            await remove_item_from_cache(gate_cache)
            continue
        except BaseException as e:
            logger.error(f"{type(e)}, {e}")
            raise


async def check_version(conn: SSHClientConnection, interpreter: str) -> None:
    """Verify that the remote Python interpreter meets FTL requirements.

    Checks that the remote Python interpreter is version 3 or greater and
    that the shell doesn't emit unexpected output that could interfere with
    FTL operations.

    Args:
        conn: Active SSH connection to the remote host.
        interpreter: Path to Python interpreter on remote host to check.

    Raises:
        Exception: If Python version is less than 3, or if non-interactive
            shell emits unexpected text that could interfere with operations.

    Example:
        >>> await check_version(conn, "/usr/bin/python3")
        # Passes silently if Python 3+ is available

    Note:
        This check ensures compatibility and prevents issues with module
        execution that requires Python 3 features.
    """
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


async def connect_ssh(host: Dict[str, str]) -> SSHClientConnection:
    """Create a basic SSH connection to a host using Ansible-style configuration.

    Establishes an SSH connection using host configuration parameters following
    Ansible conventions. Extracts connection details like hostname, port, and
    username from the host dictionary.

    Args:
        host: Dictionary containing host configuration with optional keys:
            - ansible_host: Target hostname/IP (required)
            - ansible_port: SSH port (default: 22)
            - ansible_user: SSH username (default: current user)

    Returns:
        SSHClientConnection object for the established connection.

    Example:
        >>> host_config = {
        ...     "ansible_host": "example.com",
        ...     "ansible_port": 2222,
        ...     "ansible_user": "deploy"
        ... }
        >>> conn = await connect_ssh(host_config)
        >>> # Use connection for operations
        >>> conn.close()

    Note:
        This is a lower-level function compared to connect_gate. Use connect_gate
        for full FTL functionality including gate deployment.
    """
    ssh_host = host.get("ansible_host")
    if host and host.get("ansible_port"):
        port_value = host.get("ansible_port")
        ssh_port = int(port_value) if port_value is not None else 22
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


async def mkdir(
    inventory: Dict[str, dict], gate_cache: Optional[Dict[str, Gate]], name: str
) -> None:
    """Create directories on all hosts in an inventory.

    Creates the specified directory on all hosts defined in the inventory,
    using either cached gate connections or establishing new SSH connections
    as needed. Uses SFTP for reliable directory creation.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        name: Path to the directory to create on remote hosts.

    Example:
        >>> inventory = {
        ...     "webservers": {"hosts": {"web1": {"ansible_host": "1.1.1.1"}}}
        ... }
        >>> await mkdir(inventory, {}, "/opt/myapp")
        # Creates /opt/myapp directory on all hosts

    Note:
        Creates parent directories as needed (equivalent to 'mkdir -p').
        Reuses cached connections when available for better performance.
    """
    hosts = unique_hosts(inventory)

    for host in hosts:
        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn if gate else None
        else:
            conn = await connect_ssh(hosts[host])

        if conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.makedirs(name, exist_ok=True)


def mkdir_sync(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    name: str,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Synchronous wrapper for mkdir operation.

    Provides a synchronous interface to the async mkdir function for use
    in non-async contexts. Manages event loop creation and execution.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        name: Path to the directory to create on remote hosts.
        loop: Optional asyncio event loop to use. If None, creates a new loop.

    Example:
        >>> inventory = {"web": {"hosts": {"web1": {"ansible_host": "1.1.1.1"}}}}
        >>> mkdir_sync(inventory, {}, "/var/log/myapp")
        # Synchronously creates directory on all hosts

    Note:
        Use the async version (mkdir) when possible for better performance
        in async applications.
    """
    coro = mkdir(inventory, gate_cache, name)

    if loop is None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.result()


async def copy(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
) -> Dict[str, dict]:
    """Copy files or directories to all hosts in an inventory.

    Copies the specified source file or directory to the destination path
    on all hosts defined in the inventory. Supports recursive copying for
    directories and uses SFTP for reliable transfer.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Local source file or directory path to copy.
        dest: Destination path on remote hosts.

    Returns:
        Dictionary mapping host names to operation results with 'changed' status.

    Example:
        >>> inventory = {"db": {"hosts": {"db1": {"ansible_host": "2.2.2.2"}}}}
        >>> results = await copy(inventory, {}, "/etc/myapp.conf", "/etc/myapp.conf")
        >>> print(results)
        {'db1': {'changed': True}}

    Note:
        Supports both files and directories with recursive copying.
        Reuses cached connections when available for better performance.
    """
    hosts = unique_hosts(inventory)

    results = {}

    for host in hosts:
        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn if gate else None
        else:
            conn = await connect_ssh(hosts[host])

        if conn:
            async with conn.start_sftp_client() as sftp:
                await sftp.put(src, dest, recurse=True)
            results[host] = {"changed": True}

    return results


def copy_sync(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Dict[str, dict]:
    """Synchronous wrapper for copy operation.

    Provides a synchronous interface to the async copy function for use
    in non-async contexts. Manages event loop creation and execution.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Local source file or directory path to copy.
        dest: Destination path on remote hosts.
        loop: Optional asyncio event loop to use. If None, creates a new loop.

    Returns:
        Dictionary mapping host names to operation results with 'changed' status.

    Example:
        >>> inventory = {"app": {"hosts": {"app1": {"ansible_host": "3.3.3.3"}}}}
        >>> results = copy_sync(inventory, {}, "./config.yaml", "/opt/app/config.yaml")
        >>> print(results)
        {'app1': {'changed': True}}

    Note:
        Use the async version (copy) when possible for better performance
        in async applications.
    """
    coro = copy(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def template(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
) -> Dict[str, dict]:
    """Process Jinja2 templates and deploy to all hosts in an inventory.

    Renders Jinja2 templates using host-specific variables and deploys the
    rendered content to each host. Each host gets a customized version of
    the template based on its configuration variables.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Local Jinja2 template file path.
        dest: Destination path on remote hosts for rendered template.

    Returns:
        Dictionary mapping host names to operation results with 'changed' status.

    Example:
        >>> inventory = {
        ...     "web": {
        ...         "hosts": {
        ...             "web1": {"ansible_host": "1.1.1.1", "server_name": "web1.example.com"}
        ...         }
        ...     }
        ... }
        >>> # Template file contains: server_name = {{ server_name }}
        >>> results = await template(inventory, {}, "nginx.conf.j2", "/etc/nginx/nginx.conf")
        >>> print(results)
        {'web1': {'changed': True}}

    Note:
        Templates are rendered with host variables as context. Creates temporary
        files during processing which are automatically cleaned up.
    """
    hosts = unique_hosts(inventory)

    results = {}

    environment = jinja2.Environment()

    for host_name, host in hosts.items():
        if gate_cache and host_name in gate_cache:
            gate = gate_cache.get(host_name)
            conn = gate.conn if gate else None
        else:
            conn = await connect_ssh(host)

        if conn:
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


def template_sync(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Dict[str, dict]:
    """Synchronous wrapper for template operation.

    Provides a synchronous interface to the async template function for use
    in non-async contexts. Manages event loop creation and execution.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Local Jinja2 template file path.
        dest: Destination path on remote hosts for rendered template.
        loop: Optional asyncio event loop to use. If None, creates a new loop.

    Returns:
        Dictionary mapping host names to operation results with 'changed' status.

    Example:
        >>> inventory = {"db": {"hosts": {"db1": {"ansible_host": "2.2.2.2", "db_name": "prod"}}}}
        >>> results = template_sync(inventory, {}, "my.cnf.j2", "/etc/mysql/my.cnf")
        >>> print(results)
        {'db1': {'changed': True}}

    Note:
        Use the async version (template) when possible for better performance
        in async applications.
    """
    coro = template(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def copy_from(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
) -> None:
    """Copy files or directories from remote hosts to the local system.

    Downloads the specified source file or directory from all hosts in the
    inventory to the local destination path. Supports recursive copying for
    directories and uses SFTP for reliable transfer.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Remote source file or directory path to copy from.
        dest: Local destination path for downloaded files.

    Example:
        >>> inventory = {"logs": {"hosts": {"web1": {"ansible_host": "1.1.1.1"}}}}
        >>> await copy_from(inventory, {}, "/var/log/app.log", "./logs/web1-app.log")
        # Downloads log file from remote host

    Note:
        For multiple hosts, consider using unique destination paths to avoid
        overwriting files. Supports both files and directories with recursive copying.
    """
    hosts = unique_hosts(inventory)

    for host in hosts:
        if gate_cache and host in gate_cache:
            gate = gate_cache.get(host)
            conn = gate.conn if gate else None
        else:
            conn = await connect_ssh(hosts[host])

        if conn:
            async with conn.start_sftp_client() as sftp:
                print(f"Copy from {src} to {dest}")
                await sftp.get(src, dest, recurse=True)


def copy_from_sync(
    inventory: Dict[str, dict],
    gate_cache: Optional[Dict[str, Gate]],
    src: str,
    dest: str,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Synchronous wrapper for copy_from operation.

    Provides a synchronous interface to the async copy_from function for use
    in non-async contexts. Manages event loop creation and execution.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups.
        gate_cache: Optional cache of existing gate connections to reuse.
        src: Remote source file or directory path to copy from.
        dest: Local destination path for downloaded files.
        loop: Optional asyncio event loop to use. If None, creates a new loop.

    Example:
        >>> inventory = {"backup": {"hosts": {"db1": {"ansible_host": "2.2.2.2"}}}}
        >>> copy_from_sync(inventory, {}, "/var/backups/db.sql", "./backups/db1.sql")
        # Synchronously downloads backup file

    Note:
        Use the async version (copy_from) when possible for better performance
        in async applications.
    """
    coro = copy_from(inventory, gate_cache, src, dest)

    if loop is None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.result()


async def send_gate(
    gate_builder: Callable, conn: SSHClientConnection, tempdir: str, interpreter: str
) -> str:
    """Deploy the FTL gate executable to a remote host.

    Builds and transfers the FTL gate executable to the remote host, handling
    caching to avoid unnecessary transfers. Sets proper permissions and checks
    for existing gate files to optimize deployment.

    Args:
        gate_builder: Callable that creates the gate executable and returns
            (gate_path, gate_hash) tuple.
        conn: Active SSH connection to the remote host.
        tempdir: Remote temporary directory for storing the gate file.
        interpreter: Python interpreter path for building the gate.

    Returns:
        Full path to the deployed gate file on the remote host.

    Example:
        >>> gate_path = await send_gate(build_ftl_gate, conn, "/tmp", "/usr/bin/python3")
        >>> print(f"Gate deployed to: {gate_path}")
        Gate deployed to: /tmp/ftl_gate_abc123.pyz

    Note:
        Implements intelligent caching - reuses existing gates if they exist
        and have non-zero size. Sets executable permissions (700) on the gate file.
    """
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
    """Start the FTL gate process on a remote host and establish communication.

    Launches the deployed gate executable as a remote process and performs
    the initial handshake to ensure the gate is ready for module execution.

    Args:
        conn: Active SSH connection to the remote host.
        gate_file_name: Full path to the gate executable on the remote host.

    Returns:
        SSHClientProcess object representing the running gate process.

    Raises:
        Exception: If the gate fails to start or the initial handshake fails.

    Example:
        >>> process = await open_gate(conn, "/tmp/ftl_gate_abc123.pyz")
        >>> # Gate is now ready for module execution
        >>> # Remember to close the gate when done

    Note:
        Performs initial "Hello" handshake to verify gate communication.
        The returned process should be properly closed when no longer needed.
    """
    process = await conn.create_process(gate_file_name)
    send_message_str(process.stdin, "Hello", {})
    if await read_message(process.stdout) != ["Hello", {}]:
        error = await process.stderr.read()
        logger.error(error)
        raise Exception(error)
    return process


async def remove_item_from_cache(gate_cache: Optional[Dict[str, Gate]]) -> None:
    """Remove and close a random gate connection from the cache.

    Removes one gate connection from the cache and properly closes it to
    free up resources. Used for cache management and connection cleanup
    during error recovery.

    Args:
        gate_cache: Optional cache dictionary containing gate connections.
            If None or empty, no action is taken.

    Example:
        >>> cache = {"host1": Gate(conn1, proc1, "/tmp")}
        >>> await remove_item_from_cache(cache)
        # Removes and closes one gate connection from cache

    Note:
        Removes items randomly using dict.popitem(). Properly closes the
        gate connection to prevent resource leaks.
    """
    if gate_cache is not None and gate_cache:
        item, (conn, gate_process, tempdir) = gate_cache.popitem()
        await close_gate(conn, gate_process, tempdir)
        logger.info("closed gate", item)


async def close_gate(
    conn: SSHClientConnection, gate_process: Optional[SSHClientProcess], tempdir: str
) -> None:
    """Properly close a gate connection and clean up resources.

    Sends shutdown signal to the gate process, reads any remaining stderr
    output, and closes the SSH connection. Ensures proper cleanup to prevent
    resource leaks.

    Args:
        conn: SSH connection to close.
        gate_process: Gate process to shutdown. Can be None.
        tempdir: Temporary directory path (currently unused but kept for compatibility).

    Example:
        >>> await close_gate(gate.conn, gate.gate_process, gate.temp_dir)
        # Gate connection is properly closed

    Note:
        Always closes the connection even if gate process shutdown fails.
        Safe to call with None gate_process.
    """
    try:
        if gate_process is not None:
            send_message_str(gate_process.stdin, "Shutdown", {})
        if gate_process is not None and gate_process.exit_status is not None:
            await gate_process.stderr.read()
    finally:
        conn.close()


async def run_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Any:
    """Execute a standard Ansible-compatible module through an FTL gate.

    Runs a module on the remote host via the gate process, handling both
    cached modules (already in the gate) and new modules (uploaded on demand).
    Supports all Ansible module types including binary and Python modules.

    Args:
        gate_process: Active gate process for module execution.
        module: Local path to the module file.
        module_name: Name of the module (typically basename of module path).
        module_args: Dictionary of arguments to pass to the module.

    Returns:
        Dictionary containing the module execution results, typically with
        keys like 'changed', 'msg', and module-specific output.

    Raises:
        ModuleNotFound: If module cannot be found in gate and upload fails.

    Example:
        >>> result = await run_module_through_gate(
        ...     gate_process, "/usr/lib/ansible/modules/ping.py", "ping", {}
        ... )
        >>> print(result)
        {'ping': 'pong', 'changed': False}

    Note:
        Implements smart caching - tries to run cached module first, uploads
        module if not found in gate. Handles both text and binary modules.
    """
    try:
        send_message_str(
            gate_process.stdin,
            "Module",
            dict(module_name=module_name, module_args=module_args),
        )
        result = await read_message(gate_process.stdout)
        if result:
            return process_module_result(GateMessage(*result))
        else:
            return {"error": True, "msg": "No response from gate"}
    except ModuleNotFound:
        with open(module, "rb") as f:
            module_text = base64.b64encode(f.read()).decode()
        send_message_str(
            gate_process.stdin,
            "Module",
            dict(module=module_text, module_name=module_name, module_args=module_args),
        )
        result = await read_message(gate_process.stdout)
        if result:
            return process_module_result(GateMessage(*result))
        else:
            return {"error": True, "msg": "No response from gate"}


async def run_ftl_module_through_gate(
    gate_process: SSHClientProcess, module: str, module_name: str, module_args: Dict
) -> Any:
    """Execute an FTL-native module through an FTL gate.

    Runs an FTL-specific module on the remote host via the gate process.
    FTL modules are Python modules with async main functions that return
    structured data directly without requiring Ansible compatibility layers.

    Args:
        gate_process: Active gate process for module execution.
        module: Local path to the FTL module file.
        module_name: Name of the module (typically basename of module path).
        module_args: Dictionary of arguments to pass to the module's main function.

    Returns:
        Dictionary containing the module execution results as returned by
        the module's main function.

    Example:
        >>> result = await run_ftl_module_through_gate(
        ...     gate_process, "./my_ftl_module.py", "my_ftl_module", {"param": "value"}
        ... )
        >>> print(result)
        {'result': 'success', 'data': {...}}

    Note:
        Unlike standard modules, FTL modules are always uploaded fresh and
        executed with direct Python function calls for maximum flexibility.
    """
    with open(module, "rb") as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(
        gate_process.stdin,
        "FTLModule",
        dict(module=module_text, module_name=module_name, module_args=module_args),
    )
    result = await read_message(gate_process.stdout)
    if result:
        return process_module_result(GateMessage(*result))
    else:
        return {"error": True, "msg": "No response from gate"}


async def run_module_remotely(
    host_name: str,
    host: Dict,
    module: str,
    module_args: Dict,
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder: Callable,
) -> Tuple[str, Dict]:
    """Execute a module on a remote host with comprehensive connection management.

    High-level function that orchestrates remote module execution including
    SSH connection establishment, gate deployment, module execution, and
    connection caching. Handles all aspects of remote automation tasks.

    Args:
        host_name: Name/identifier of the target host.
        host: Dictionary containing host configuration (ansible_host, ansible_port, etc.).
        module: Local path to the module file to execute.
        module_args: Dictionary of arguments to pass to the module.
        remote_runner: Function to execute the module (e.g., run_module_through_gate).
        gate_cache: Optional cache for reusing gate connections across calls.
        gate_builder: Callable that creates gate executables.

    Returns:
        Tuple of (host_name, execution_results) where execution_results is a
        dictionary containing the module's output.

    Example:
        >>> result = await run_module_remotely(
        ...     "web1", {"ansible_host": "1.1.1.1"}, "./ping.py", {},
        ...     run_module_through_gate, {}, build_ftl_gate
        ... )
        >>> host, output = result
        >>> print(f"{host}: {output}")
        web1: {'ping': 'pong', 'changed': False}

    Note:
        Manages gate cache automatically - reuses cached connections when available
        and caches new connections for future use. Includes retry logic for
        connection failures.
    """
    module_name = os.path.basename(module)

    ssh_host = (
        str(host.get("ansible_host"))
        if host and host.get("ansible_host")
        else host_name
    )
    ssh_port = (
        int(host.get("ansible_port", 22)) if host and host.get("ansible_port") else 22
    )
    ssh_user = (
        str(host.get("ansible_user"))
        if host and host.get("ansible_user")
        else getuser()
    )
    interpreter = (
        str(host.get("ansible_python_interpreter"))
        if host and host.get("ansible_python_interpreter")
        else sys.executable
    )

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
