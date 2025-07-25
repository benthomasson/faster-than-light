import glob
import os
import shutil
import json

from typing import List, Union, Dict
from .message import GateMessage
from .exceptions import ModuleNotFound


def ensure_directory(d: str) -> str:
    """Ensure a directory exists, creating it if necessary.
    
    Expands user home directory (~) and converts to absolute path before
    creating the directory structure if it doesn't exist.
    
    Args:
        d: Directory path to ensure exists. Can contain ~ for home directory.
    
    Returns:
        The absolute path to the ensured directory.
    
    Example:
        >>> ensure_directory("~/.ftl")
        '/home/user/.ftl'
    """
    d = os.path.abspath(os.path.expanduser(d))
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def chunk(lst: List, n: int):
    """Split a list into chunks of maximum size n.
    
    Yields successive chunks from the input list, where each chunk contains
    at most n elements. The last chunk may contain fewer elements if the
    list length is not evenly divisible by n.
    
    Args:
        lst: List to be chunked into smaller pieces.
        n: Maximum size of each chunk.
    
    Yields:
        List: Successive chunks of the input list.
    
    Example:
        >>> list(chunk([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


def find_module(module_dirs: List[str], module_name: str) -> Union[str, None]:
    """Find a module file by searching through multiple directories.
    
    Searches for a module in the provided directories, looking first for
    Python files (module_name.py) and then for binary modules (module_name).
    Returns the path to the first matching module found.
    
    Args:
        module_dirs: List of directory paths to search in. Empty or None
            entries are skipped.
        module_name: Name of the module to find (without .py extension).
    
    Returns:
        Path to the found module file, or None if not found in any directory.
    
    Example:
        >>> find_module(["/usr/lib/modules", "/opt/modules"], "ping")
        '/usr/lib/modules/ping.py'
    """

    module = None

    # Find the module in module_dirs
    for d in module_dirs:
        if not d:
            continue
        module = os.path.join(d, f"{module_name}.py")
        if os.path.exists(module):
            break
        else:
            module = None

    # Look for binary module in module_dirs
    if module is None:
        for d in module_dirs:
            if not d:
                continue
            module = os.path.join(d, module_name)
            if os.path.exists(module):
                break
            else:
                module = None

    return module


def read_module(module_dirs: List[str], module_name: str) -> bytes:
    """Read the contents of a module file as bytes.
    
    Locates a module using find_module() and reads its entire contents
    in binary mode. This supports both Python modules and binary executables.
    
    Args:
        module_dirs: List of directory paths to search in.
        module_name: Name of the module to read (without .py extension).
    
    Returns:
        The complete file contents as bytes.
    
    Raises:
        ModuleNotFound: If the module cannot be found in any of the
            provided directories.
    
    Example:
        >>> content = read_module(["/usr/lib/modules"], "ping")
        >>> len(content) > 0
        True
    """
    module = find_module(module_dirs, module_name)

    if module:
        with open(module, "rb") as f:
            return f.read()
    else:
        raise ModuleNotFound(f"Cannot find {module_name} in {module_dirs}")


def clean_up_ftl_cache() -> None:
    """Remove the FTL cache directory and all its contents.
    
    Deletes the ~/.ftl directory which contains cached gate files and other
    FTL artifacts. Includes safety checks to ensure only the FTL cache 
    directory is removed.
    
    Note:
        This operation is irreversible and will force regeneration of all
        cached gate files on next use.
    
    Example:
        >>> clean_up_ftl_cache()  # Removes ~/.ftl directory
    """
    cache = os.path.abspath(os.path.expanduser("~/.ftl"))
    if os.path.exists(cache) and os.path.isdir(cache) and ".ftl" in cache:
        shutil.rmtree(cache)


def clean_up_tmp() -> None:
    """Remove temporary FTL directories from /tmp.
    
    Finds and removes all directories matching the pattern "/tmp/ftl-*".
    Includes safety checks to ensure only FTL temporary directories are
    removed by verifying both "tmp" and "ftl" are in the path.
    
    Note:
        This cleans up temporary directories that may be left behind from
        interrupted FTL operations.
    
    Example:
        >>> clean_up_tmp()  # Removes /tmp/ftl-* directories
    """
    for d in glob.glob("/tmp/ftl-*"):
        if os.path.exists(d) and os.path.isdir(d) and "tmp" in d and "ftl" in d:
            shutil.rmtree(d)


def process_module_result(message: GateMessage) -> Dict:
    """Process a gate message and extract module execution results.
    
    Parses different types of gate messages and converts them into a
    standardized dictionary format. Handles both successful results and
    various error conditions.
    
    Args:
        message: A GateMessage tuple containing message type and data.
    
    Returns:
        Dictionary containing the processed result. For successful module
        execution, contains the parsed output. For errors, contains error
        information with appropriate structure.
    
    Raises:
        Exception: If message is None, empty, or contains unsupported
            message type.
        ModuleNotFound: If the message indicates a module was not found
            in the gate bundle.
    
    Message Types Handled:
        - "ModuleResult": Standard module execution result
        - "FTLModuleResult": FTL-specific module result
        - "GateSystemError": System-level gate errors
        - "ModuleNotFound": Module not found in gate
    
    Example:
        >>> msg = ("ModuleResult", {"stdout": '{"changed": true}'})
        >>> process_module_result(msg)
        {'changed': True}
    """
    if message is None:
        raise Exception(f"Null message")
    if len(message) == 0:
        raise Exception(f"Empty message")
    msg_type = message[0]
    if msg_type == "ModuleResult":
        if message[1].get("stdout", None):
            return json.loads(message[1]["stdout"])
        else:
            return dict(error=dict(message=message[1]["stderr"]))
    if msg_type == "FTLModuleResult":
        if message[1].get("result", None):
            return message[1]["result"]
    elif msg_type == "GateSystemError":
        return dict(error=dict(error_type=message[0], message=message[1]))
    elif msg_type == "ModuleNotFound":
        raise ModuleNotFound(message[1]['message'])
    else:
        raise Exception(f"Unsupported message type {msg_type}")


def unique_hosts(inventory: Dict) -> Dict:
    """Extract unique hosts from an Ansible-style inventory.
    
    Flattens an inventory structure by collecting all hosts from all groups
    into a single dictionary. If a host appears in multiple groups, only
    one instance is kept (the last one encountered).
    
    Args:
        inventory: Ansible-style inventory dictionary with groups containing
            hosts. Expected structure:
            {
                "group_name": {
                    "hosts": {
                        "host_name": host_config_dict
                    }
                }
            }
    
    Returns:
        Dictionary mapping host names to their configuration dictionaries.
        
    Example:
        >>> inv = {
        ...     "webservers": {"hosts": {"web1": {"ip": "1.1.1.1"}}},
        ...     "databases": {"hosts": {"db1": {"ip": "2.2.2.2"}}}
        ... }
        >>> unique_hosts(inv)
        {'web1': {'ip': '1.1.1.1'}, 'db1': {'ip': '2.2.2.2'}}
    """
    hosts = {}

    for group_name, group in inventory.items():
        for host_name, host in group.get("hosts").items():
            hosts[host_name] = host

    return hosts
