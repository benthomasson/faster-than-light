import asyncio
from functools import partial

from .gate import build_ftl_gate
from .util import chunk, find_module
from .types import Gate
from .ssh import run_module_through_gate, run_ftl_module_through_gate, run_module_remotely
from .local import run_module_locally, run_ftl_module_locally
from .exceptions import ModuleNotFound

from typing import Dict, Optional, Callable, List, Tuple
from asyncio.tasks import Task


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


async def run_module_on_host(
    host_name: str,
    host: Dict,
    module: str,
    module_args: Dict,
    local_runner: Callable,
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder: Callable,
) -> Tuple[str, Dict]:
    if host and host.get("ansible_connection") == "local":
        return await local_runner(host_name, host, module, module_args)
    else:
        return await run_module_remotely(host_name, host, module, module_args, remote_runner, gate_cache, gate_builder)


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
        raise ModuleNotFound(f"Module {module_name} not found in {module_dirs}")

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


def run_module_sync(
    inventory: Dict,
    module_dirs: List[str],
    module_name: str,
    gate_cache: Optional[Dict[str, Gate]] = None,
    modules: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    module_args: Optional[Dict] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None
) -> Dict[str, Dict]:
    """
    Runs a module on all items in an inventory concurrently.
    """

    if loop is None:
        if gate_cache is not None:
            print('Gate cache is not supported without loop. Start a new event loop and run it in a separate thread.')
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
    )

    if loop is None:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


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
