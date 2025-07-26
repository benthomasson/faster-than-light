"""Module execution orchestration and inventory management for FTL.

This module provides the core orchestration logic for running automation modules
across inventories of hosts. It handles both local and remote execution, manages
connection pooling, processes variable references, and coordinates concurrent
module execution with chunking for optimal performance.

Key Features:
- Concurrent module execution across multiple hosts
- Intelligent chunking to optimize remote connection usage
- Variable reference resolution using the Ref system
- Host-specific argument override support
- Gate connection caching and reuse
- Support for both Ansible-compatible and FTL-native modules
- Flexible local/remote execution based on host configuration
- Error handling and result aggregation

The module system supports complex automation workflows with:
- Dynamic variable dereferencing for flexible configuration
- Per-host argument customization
- Connection pooling for performance optimization
- Graceful error handling and reporting
- Both synchronous and asynchronous execution patterns
"""

import asyncio
from asyncio.tasks import Task
from functools import partial
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .exceptions import ModuleNotFound
from .gate import build_ftl_gate
from .local import run_ftl_module_locally, run_module_locally
from .ref import Ref, deref
from .ssh import (
    run_ftl_module_through_gate,
    run_module_remotely,
    run_module_through_gate,
)
from .types import Gate
from .util import chunk, find_module, unique_hosts


def extract_task_results(tasks: List[Tuple[str, Task]]) -> Dict[str, Dict[str, Any]]:
    """Extract and aggregate results from completed asyncio tasks.

    Processes a list of completed asyncio tasks that represent module executions
    on different hosts. Extracts successful results and converts exceptions into
    error entries with consistent formatting.

    Args:
        tasks: List of (host_name, Task) tuples where each Task represents
            a completed module execution. Tasks should return (host_name, result)
            tuples on success.

    Returns:
        Dictionary mapping host names to their execution results. Each result
        is a dictionary containing either:
        - Module execution results (varies by module)
        - Error information: {"error": True, "msg": "error description"}

    Example:
        >>> import asyncio
        >>> async def mock_task():
        ...     return ("web1", {"changed": True, "msg": "success"})
        >>> task = asyncio.create_task(mock_task())
        >>> await task  # Let it complete
        >>> extract_task_results([("web1", task)])
        {'web1': {'changed': True, 'msg': 'success'}}

        # Error handling
        >>> async def failing_task():
        ...     raise Exception("Connection failed")
        >>> task = asyncio.create_task(failing_task())
        >>> # Let it complete with exception
        >>> extract_task_results([("web2", task)])
        {'web2': {'error': True, 'msg': 'Connection failed'}}

    Note:
        This function assumes tasks have already completed. It's typically called
        after asyncio.gather() has finished executing all tasks. Exceptions are
        caught and converted to error dictionaries for consistent result format.
    """
    results = {}
    for host_name, task in tasks:
        try:
            host_name, result = task.result()
            results[host_name] = result
        except BaseException as e:
            results[host_name] = {"error": True, "msg": str(e)}
    return results


async def run_module_on_host(
    host_name: str,
    host: Dict[str, Any],
    module: str,
    module_args: Dict[str, Any],
    local_runner: Callable[
        [str, Dict[str, Any], str, Dict[str, Any]],
        Awaitable[Tuple[str, Dict[str, Any]]],
    ],
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder: Callable[..., Tuple[str, str]],
) -> Tuple[str, Dict[str, Any]]:
    """Execute a module on a single host, choosing local or remote execution.

    Determines the appropriate execution method (local or remote) based on host
    configuration and delegates to the appropriate runner function. This provides
    a unified interface for module execution regardless of the target location.

    Args:
        host_name: Name/identifier of the target host for execution.
        host: Dictionary containing host configuration including connection
            settings like 'ansible_connection', 'ansible_host', etc.
        module: Local file path to the module to execute.
        module_args: Dictionary of arguments to pass to the module.
        local_runner: Callable for executing modules locally. Should match
            the signature of run_module_locally or run_ftl_module_locally.
        remote_runner: Callable for executing modules through gates. Should
            match the signature of run_module_through_gate or similar.
        gate_cache: Optional cache for reusing gate connections across calls.
            Used only for remote execution.
        gate_builder: Callable that creates gate executables for remote hosts.
            Used only for remote execution.

    Returns:
        Tuple of (host_name, execution_results) where execution_results is a
        dictionary containing the module's output.

    Example:
        >>> host_config = {"ansible_connection": "local"}
        >>> result = await run_module_on_host(
        ...     "localhost", host_config, "./ping.py", {},
        ...     run_module_locally, run_module_through_gate, {}, build_ftl_gate
        ... )
        >>> host, output = result
        >>> print(f"{host}: {output}")
        localhost: {'ping': 'pong', 'changed': False}

        # Remote execution
        >>> remote_host = {"ansible_host": "192.168.1.100"}
        >>> result = await run_module_on_host(
        ...     "web1", remote_host, "./ping.py", {},
        ...     run_module_locally, run_module_through_gate, {}, build_ftl_gate
        ... )

    Note:
        Local execution is triggered by setting 'ansible_connection' to 'local'
        in the host configuration. All other configurations default to remote
        execution through SSH gates.
    """
    if host and host.get("ansible_connection") == "local":
        return await local_runner(host_name, host, module, module_args)
    else:
        return await run_module_remotely(
            host_name,
            host,
            module,
            module_args,
            remote_runner,
            gate_cache,
            gate_builder,
        )


async def _run_module(
    inventory: Dict[str, Any],
    module_dirs: List[str],
    module_name: str,
    local_runner: Callable[
        [str, Dict[str, Any], str, Dict[str, Any]],
        Awaitable[Tuple[str, Dict[str, Any]]],
    ],
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    modules: Optional[List[str]],
    dependencies: Optional[List[str]],
    module_args: Optional[Dict[str, Any]],
    host_args: Optional[Dict[str, Dict[str, Any]]],
    use_gate: Optional[Callable[..., Tuple[str, str]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Core implementation for running modules across an inventory of hosts.

    This is the central orchestration function that coordinates module execution
    across multiple hosts with sophisticated features including variable reference
    resolution, host-specific argument overrides, connection chunking for optimal
    performance, and comprehensive error handling.

    Key Features:
    - Concurrent execution with intelligent chunking (10 hosts per chunk)
    - Variable reference (Ref) resolution for dynamic configuration
    - Host-specific argument overrides with proper precedence
    - Gate connection caching and reuse for performance
    - Flexible gate builder configuration
    - Comprehensive error handling and result aggregation

    Args:
        inventory: Ansible-style inventory dictionary containing host groups
            and host configurations. Structure: {"group": {"hosts": {"host": config}}}
        module_dirs: List of directories to search for the specified module.
            Searched in order until module is found.
        module_name: Name of the module to execute. Must exist in one of the
            module_dirs.
        local_runner: Callable for executing modules locally (e.g., run_module_locally).
        remote_runner: Callable for executing modules through gates
            (e.g., run_module_through_gate).
        gate_cache: Optional cache for reusing gate connections across hosts.
            Improves performance for multi-host operations.
        modules: Optional list of additional modules to include in gate builds.
            The target module_name is automatically added if not present.
        dependencies: Optional list of Python dependencies to install in gates.
        module_args: Optional dictionary of arguments to pass to all modules.
            Supports Ref objects for dynamic variable resolution.
        host_args: Optional dictionary mapping host names to host-specific
            argument overrides. Has higher precedence than module_args.
        use_gate: Optional custom gate builder function. If None, uses the
            default build_ftl_gate with provided modules and dependencies.

    Returns:
        Dictionary mapping host names to their execution results. Each result
        contains either module output or error information:
        - Success: Module-specific output dictionary
        - Error: {"error": True, "msg": "error description"}

    Raises:
        ModuleNotFound: If the specified module cannot be found in any module_dirs.

    Example:
        >>> inventory = {
        ...     "webservers": {
        ...         "hosts": {
        ...             "web1": {"ansible_host": "192.168.1.10"},
        ...             "web2": {"ansible_host": "192.168.1.11"}
        ...         }
        ...     }
        ... }
        >>> module_args = {"msg": "Hello from FTL"}
        >>> host_args = {"web1": {"msg": "Special message for web1"}}
        >>> results = await _run_module(
        ...     inventory, ["/usr/lib/ftl/modules"], "debug",
        ...     run_module_locally, run_module_through_gate,
        ...     {}, [], [], module_args, host_args
        ... )
        >>> print(results)
        {
            'web1': {'changed': False, 'msg': 'Special message for web1'},
            'web2': {'changed': False, 'msg': 'Hello from FTL'}
        }

        # With variable references
        >>> from faster_than_light.ref import Ref
        >>> config = Ref(None, "config")
        >>> module_args = {"dest": config.app.log_path}
        >>> # Each host's config.app.log_path value will be resolved

    Note:
        - Hosts are processed in chunks of 10 for optimal performance
        - Variable references (Ref objects) are resolved per-host
        - Host-specific args override module args and resolved refs
        - Local execution is used when ansible_connection="local"
        - Gate connections are cached and reused across calls
        - All exceptions are caught and converted to error results
    """

    module = find_module(module_dirs, module_name)

    if modules is None:
        modules = []
    if module_name not in modules:
        modules.append(module_name)

    if module is None:
        raise ModuleNotFound(f"Module {module_name} not found in {module_dirs}")

    hosts = unique_hosts(inventory)

    if use_gate:
        gate_builder = use_gate
    else:
        gate_builder = partial(
            build_ftl_gate,
            modules=modules,
            module_dirs=module_dirs,
            dependencies=dependencies,
        )

    # support refs only at the top level of arg values
    has_refs = False
    if module_args:
        for arg_name, arg_value in module_args.items():
            if isinstance(arg_value, Ref):
                has_refs = True

    all_tasks = []
    # Run the tasks in chunks of 10 to reduce contention for remote connections.
    # This doubles performance at num_hosts=1000 for remote execution
    for c in chunk(list(hosts.items()), 10):
        tasks = []
        for host_name, host in c:
            host_specific_args = {}
            if host_args:
                host_specific_args = host_args.get(host_name, {})
            if host_specific_args or has_refs:
                # make a copy of module_args since we need to modify it
                merged_args = module_args.copy() if module_args else {}
                # refs have lower precedence than host specific args
                if module_args:
                    for arg_name, arg_value in module_args.items():
                        merged_args[arg_name] = deref(host, arg_value)
                # host specific args have higher precedence than refs
                merged_args.update(host_specific_args)
            else:
                # no host specific args so just reuse module_args
                merged_args = module_args or {}
            tasks.append(
                (
                    host_name,
                    asyncio.create_task(
                        run_module_on_host(
                            host_name,
                            host,
                            module,
                            merged_args,
                            local_runner,
                            remote_runner,
                            gate_cache,
                            gate_builder,
                        )
                    ),
                )
            )
        await asyncio.gather(*[task[1] for task in tasks], return_exceptions=True)
        all_tasks.extend(tasks)

    return extract_task_results(all_tasks)


async def run_module(
    inventory: Dict[str, Any],
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict[str, Any]] = None,
    host_args: Optional[Dict[str, Dict[str, Any]]] = None,
    use_gate: Optional[Callable[..., Tuple[str, str]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute an Ansible-compatible module across all hosts in an inventory.

    This is the primary async interface for running standard automation modules
    (Ansible-compatible) across multiple hosts concurrently. It provides a
    high-level API with support for variable references, host-specific overrides,
    and optimal performance through connection caching and chunked execution.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups
            and configurations. Format: {"group": {"hosts": {"hostname": config}}}
        module_dirs: List of directories to search for the module. Searched
            in order until the module is found.
        module_name: Name of the module to execute. Must be found in one of
            the module_dirs.
        gate_cache: Optional cache for SSH gate connections. Reusing this
            cache across calls improves performance significantly.
        modules: Optional list of additional modules to bundle in remote gates.
            Useful for modules with dependencies on other modules.
        dependencies: Optional list of Python package dependencies to install
            in remote gates (e.g., ["requests", "pyyaml"]).
        module_args: Optional dictionary of arguments to pass to the module.
            Supports Ref objects for dynamic variable resolution per host.
        host_args: Optional dictionary mapping specific host names to custom
            arguments. These override any matching keys in module_args.
        use_gate: Optional custom gate builder function. If provided, replaces
            the default gate building logic.

    Returns:
        Dictionary mapping host names to their execution results:
        - Successful execution: Module-specific output (varies by module)
        - Failed execution: {"error": True, "msg": "error description"}

    Raises:
        ModuleNotFound: If the specified module cannot be found in module_dirs.

    Example:
        >>> # Basic module execution
        >>> inventory = {
        ...     "webservers": {
        ...         "hosts": {
        ...             "web1": {"ansible_host": "192.168.1.10"},
        ...             "web2": {"ansible_host": "192.168.1.11"}
        ...         }
        ...     }
        ... }
        >>> results = await run_module(
        ...     inventory, ["/usr/lib/ansible/modules"], "ping"
        ... )
        >>> print(results)
        {'web1': {'ping': 'pong'}, 'web2': {'ping': 'pong'}}

        # With module arguments and host-specific overrides
        >>> module_args = {"src": "/etc/hosts", "dest": "/tmp/hosts"}
        >>> host_args = {"web1": {"dest": "/tmp/hosts-web1"}}
        >>> results = await run_module(
        ...     inventory, ["/usr/lib/ansible/modules"], "copy",
        ...     module_args=module_args, host_args=host_args
        ... )

        # With variable references
        >>> from faster_than_light.ref import Ref
        >>> config = Ref(None, "config")
        >>> module_args = {"dest": config.app.config_path}
        >>> # Each host's config.app.config_path will be resolved differently

    Note:
        - Executes Ansible-compatible modules (Python scripts with JSON args)
        - Use run_ftl_module() for FTL-native modules with async main functions
        - Gate connections are automatically cached and reused for performance
        - Hosts are processed in optimal chunks for connection efficiency
        - Variable references are resolved per-host for flexible configuration
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
        host_args,
        use_gate,
    )


def run_module_sync(
    inventory: Dict[str, Any],
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict[str, Any]] = None,
    host_args: Optional[Dict[str, Dict[str, Any]]] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    use_gate: Optional[Callable[..., Tuple[str, str]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute an Ansible-compatible module synchronously across an inventory.

    Synchronous wrapper for run_module() that provides a blocking interface
    for non-async contexts. Manages event loop creation and execution, making
    it suitable for use in traditional synchronous applications, scripts,
    and interactive environments.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups
            and configurations. Format: {"group": {"hosts": {"hostname": config}}}
        module_dirs: List of directories to search for the module. Searched
            in order until the module is found.
        module_name: Name of the module to execute. Must be found in one of
            the module_dirs.
        gate_cache: Optional cache for SSH gate connections. Note: If no event
            loop is provided, gate caching is disabled for thread safety.
        modules: Optional list of additional modules to bundle in remote gates.
        dependencies: Optional list of Python package dependencies to install
            in remote gates.
        module_args: Optional dictionary of arguments to pass to the module.
            Supports Ref objects for dynamic variable resolution per host.
        host_args: Optional dictionary mapping specific host names to custom
            arguments. These override any matching keys in module_args.
        loop: Optional asyncio event loop to use. If None, creates a new loop.
            Required if you want to reuse gate_cache across multiple calls.
        use_gate: Optional custom gate builder function.

    Returns:
        Dictionary mapping host names to their execution results:
        - Successful execution: Module-specific output (varies by module)
        - Failed execution: {"error": True, "msg": "error description"}

    Raises:
        ModuleNotFound: If the specified module cannot be found in module_dirs.

    Example:
        >>> # Basic synchronous execution
        >>> inventory = {
        ...     "databases": {
        ...         "hosts": {"db1": {"ansible_host": "192.168.1.20"}}
        ...     }
        ... }
        >>> results = run_module_sync(
        ...     inventory, ["/usr/lib/ansible/modules"], "ping"
        ... )
        >>> print(results)
        {'db1': {'ping': 'pong'}}

        # With persistent event loop for gate caching
        >>> import asyncio
        >>> loop = asyncio.new_event_loop()
        >>> gate_cache = {}
        >>>
        >>> # Multiple calls reuse the same gates
        >>> results1 = run_module_sync(
        ...     inventory, ["/usr/lib/ansible/modules"], "setup",
        ...     gate_cache=gate_cache, loop=loop
        ... )
        >>> results2 = run_module_sync(
        ...     inventory, ["/usr/lib/ansible/modules"], "ping",
        ...     gate_cache=gate_cache, loop=loop
        ... )
        >>> # Gate connections are reused between calls

        # Interactive scripting usage
        >>> module_args = {"name": "nginx", "state": "started"}
        >>> results = run_module_sync(
        ...     inventory, ["/usr/lib/ansible/modules"], "service",
        ...     module_args=module_args
        ... )

    Note:
        - Use run_module() instead when already in an async context
        - Gate caching requires providing an event loop parameter
        - Creates a new event loop if none provided (slower but simpler)
        - Ideal for CLI tools, scripts, and non-async applications
        - All async benefits (chunking, concurrency) are preserved
    """

    if loop is None:
        if gate_cache is not None:
            print(
                "Gate cache is not supported without loop. Start a new event loop and run it in a separate thread."
            )
        gate_cache = {}

    coro = _run_module(
        inventory,
        module_dirs,
        module_name,
        run_module_locally,
        run_module_through_gate,
        gate_cache,
        modules,
        dependencies,
        module_args,
        host_args,
        use_gate,
    )

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


async def run_ftl_module(
    inventory: Dict[str, Any],
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict[str, Any]] = None,
    host_args: Optional[Dict[str, Dict[str, Any]]] = None,
    use_gate: Optional[Callable[..., Tuple[str, str]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Execute an FTL-native module across all hosts in an inventory.

    This is the primary async interface for running FTL-native modules across
    multiple hosts concurrently. FTL modules are Python files with async main
    functions that provide direct integration with FTL's async architecture,
    offering better performance and more flexible return value handling than
    traditional Ansible modules.

    Args:
        inventory: Ansible-style inventory dictionary containing host groups
            and configurations. Format: {"group": {"hosts": {"hostname": config}}}
        module_dirs: List of directories to search for the module. Searched
            in order until the module is found.
        module_name: Name of the FTL module to execute. Must be found in one
            of the module_dirs and contain an async main() function.
        gate_cache: Optional cache for SSH gate connections. Reusing this
            cache across calls improves performance significantly.
        modules: Optional list of additional modules to bundle in remote gates.
            Useful for modules with dependencies on other modules.
        dependencies: Optional list of Python package dependencies to install
            in remote gates (e.g., ["aiohttp", "asyncpg"]).
        module_args: Optional dictionary of arguments to pass to the module's
            main() function. Supports Ref objects for dynamic variable resolution.
        host_args: Optional dictionary mapping specific host names to custom
            arguments. These override any matching keys in module_args.
        use_gate: Optional custom gate builder function. If provided, replaces
            the default gate building logic.

    Returns:
        Dictionary mapping host names to their execution results:
        - Successful execution: Return value from module's main() function
        - Failed execution: {"error": True, "msg": "error description"}

    Raises:
        ModuleNotFound: If the specified module cannot be found in module_dirs.

    Example:
        >>> # Basic FTL module execution
        >>> inventory = {
        ...     "api_servers": {
        ...         "hosts": {
        ...             "api1": {"ansible_host": "192.168.1.30"},
        ...             "api2": {"ansible_host": "192.168.1.31"}
        ...         }
        ...     }
        ... }
        >>>
        >>> # FTL module with async main function
        >>> # File: /opt/ftl/modules/health_check.py
        >>> # async def main(host, **args):
        >>> #     async with aiohttp.ClientSession() as session:
        >>> #         url = f"http://{host['ansible_host']}:8080/health"
        >>> #         async with session.get(url) as resp:
        >>> #             return {"status": resp.status, "healthy": resp.status == 200}
        >>>
        >>> results = await run_ftl_module(
        ...     inventory, ["/opt/ftl/modules"], "health_check"
        ... )
        >>> print(results)
        {
            'api1': {'status': 200, 'healthy': True},
            'api2': {'status': 503, 'healthy': False}
        }

        # With module arguments
        >>> module_args = {"timeout": 30, "retries": 3}
        >>> results = await run_ftl_module(
        ...     inventory, ["/opt/ftl/modules"], "deploy_app",
        ...     module_args=module_args
        ... )

        # With variable references and dependencies
        >>> from faster_than_light.ref import Ref
        >>> config = Ref(None, "deployment")
        >>> module_args = {
        ...     "app_version": config.version,
        ...     "environment": config.env
        ... }
        >>> dependencies = ["aiofiles", "pydantic"]
        >>> results = await run_ftl_module(
        ...     inventory, ["/opt/ftl/modules"], "advanced_deploy",
        ...     module_args=module_args, dependencies=dependencies
        ... )

    Note:
        - FTL modules must have an async main() function signature
        - Modules receive host configuration and custom args as parameters
        - Use run_module() for standard Ansible-compatible modules
        - FTL modules can return any JSON-serializable data structure
        - Better performance than Ansible modules due to native async support
        - Ideal for complex operations requiring async libraries (HTTP, database, etc.)
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
        host_args,
        use_gate,
    )
