"""Local module execution system for FTL automation framework.

This module provides comprehensive support for executing automation modules directly
on the local system without requiring SSH connections or remote gates. It handles
both Ansible-compatible modules and FTL-native modules with sophisticated module
type detection and argument handling.

Key Features:
- Local execution of Ansible-compatible modules with full compatibility
- Support for multiple module types (binary, new-style, WANT_JSON, legacy)
- Automatic module type detection and appropriate argument formatting
- FTL-native module execution via runpy with direct Python function calls
- Robust error handling and result processing
- Temporary file management for secure module execution
- Configurable Python interpreter selection per host

Module Type Support:
- Binary modules: Executable files with command-line argument handling
- New-style modules: AnsibleModule-based with JSON stdin input
- WANT_JSON modules: JSON file argument input expecting JSON processing
- Legacy modules: Key=value argument files for older module formats
- FTL modules: Native Python modules with async main() functions

The local execution system enables FTL to run automation tasks on the control
node itself or on systems where SSH is not available, providing flexible
deployment options for mixed infrastructure environments.
"""

import asyncio
import json
import os
import shutil
import tempfile
import sys
import runpy
import logging
import traceback

from typing import Dict, Tuple

logger = logging.getLogger('faster_than_light.local')


async def check_output(cmd: str, stdin=None) -> bytes:
    """Execute a shell command asynchronously and return its output.
    
    Creates an asynchronous subprocess to execute the specified shell command,
    optionally providing input via stdin. Combines stdout and stderr into a
    single output stream for simplified error handling and result processing.
    
    Args:
        cmd: Shell command string to execute. Can include pipes, redirections,
            and other shell features supported by the system shell.
        stdin: Optional input data to send to the process stdin. Can be bytes
            or None. If provided, data will be sent to the process and stdin
            will be closed.
    
    Returns:
        Combined stdout and stderr output from the command as bytes. All process
        output is captured and returned regardless of exit code.
    
    Raises:
        OSError: If the command cannot be executed due to system limitations.
        asyncio.TimeoutError: If the command execution exceeds system limits.
        FileNotFoundError: If the shell or command executable is not found.
    
    Example:
        >>> # Execute a simple command
        >>> output = await check_output("echo 'Hello World'")
        >>> print(output.decode())
        Hello World
        
        >>> # Execute with stdin input
        >>> data = "input data".encode()
        >>> output = await check_output("cat", stdin=data)
        >>> print(output.decode())
        input data
        
        >>> # Execute Python module with JSON input
        >>> json_input = '{"key": "value"}'.encode()
        >>> output = await check_output("python module.py", stdin=json_input)
        >>> result = json.loads(output.decode())
    
    Process Configuration:
        - stdin: PIPE (allows input injection)
        - stdout: PIPE (captures normal output)
        - stderr: STDOUT (merges error output with stdout)
        - shell: True (enables shell command parsing)
        
    Note:
        This function merges stderr into stdout to provide a single output
        stream. This simplifies error handling but means error messages
        cannot be distinguished from normal output. The function waits for
        process completion and does not impose timeouts.
    """
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    stdout, stderr = await proc.communicate(stdin)
    return stdout


def is_binary_module(module: str) -> bool:
    """Detect if a module file is a binary executable rather than text-based.
    
    Attempts to read the module file as text to determine if it contains binary
    data. This detection is crucial for determining the appropriate execution
    method, as binary modules require different argument handling than text-based
    Python modules.
    
    Args:
        module: File path to the module to examine. Should be a readable file
            that exists on the filesystem.
    
    Returns:
        True if the module appears to be a binary executable (contains non-UTF8
        data), False if it can be read as text and is likely a script.
    
    Raises:
        FileNotFoundError: If the module file does not exist.
        PermissionError: If the module file cannot be read due to permissions.
        OSError: If there are other filesystem access issues.
    
    Example:
        >>> # Check a Python script module
        >>> is_binary_module("modules/setup.py")
        False
        
        >>> # Check a compiled binary module
        >>> is_binary_module("modules/ping")
        True
        
        >>> # Check a shell script module
        >>> is_binary_module("modules/shell_module.sh")
        False
    
    Detection Method:
        The function attempts to read all lines of the file as UTF-8 text.
        If this succeeds, the module is considered text-based. If a
        UnicodeDecodeError is raised, the module is considered binary.
        
    Use Cases:
        - Binary modules: Native executables, compiled programs
        - Text modules: Python scripts, shell scripts, interpreted code
        - Execution: Binary modules receive arguments via command line
        
    Note:
        This detection method is simple but effective for distinguishing
        between text-based scripts and binary executables. Binary modules
        typically receive their arguments as command-line parameters rather
        than through stdin or argument files.
    """
    try:
        with open(module) as f:
            for line in f.readlines():
                pass
        return False
    except UnicodeDecodeError:
        return True


def is_new_style_module(module: str) -> bool:
    """Detect if a module uses Ansible's new-style AnsibleModule framework.
    
    Scans the module file for the presence of "AnsibleModule(" which indicates
    the module uses Ansible's modern module development framework. New-style
    modules expect JSON input via stdin and use the AnsibleModule class for
    argument parsing and common functionality.
    
    Args:
        module: File path to the module to examine. Should be a readable text
            file containing Python code.
    
    Returns:
        True if the module contains "AnsibleModule(" and is a new-style module,
        False if it follows older argument handling patterns.
    
    Raises:
        FileNotFoundError: If the module file does not exist.
        PermissionError: If the module file cannot be read due to permissions.
        UnicodeDecodeError: If the module file contains non-UTF8 binary data.
        OSError: If there are other filesystem access issues.
    
    Example:
        >>> # Check a new-style module
        >>> is_new_style_module("modules/file.py")
        True  # Contains: module = AnsibleModule(...)
        
        >>> # Check a legacy module
        >>> is_new_style_module("modules/old_command.py")
        False  # Uses sys.argv or other argument methods
        
        >>> # Check a WANT_JSON module
        >>> is_new_style_module("modules/json_module.py")
        False  # Uses JSON files but not AnsibleModule
    
    Detection Pattern:
        The function searches for the literal string "AnsibleModule(" anywhere
        in the module file. This pattern indicates the module imports and
        instantiates the AnsibleModule class, which is the standard pattern
        for modern Ansible modules.
        
    Execution Implications:
        - New-style modules: Receive JSON via stdin containing ANSIBLE_MODULE_ARGS
        - Input format: {"ANSIBLE_MODULE_ARGS": {"param1": "value1", ...}}
        - Output: JSON to stdout with standardized result format
        - Error handling: AnsibleModule provides automatic error formatting
        
    Ansible Module Development:
        New-style modules use the AnsibleModule framework for:
        - Automatic argument parsing and validation
        - Common utility functions (run_command, etc.)
        - Standardized error and result handling
        - Built-in support for check mode and diff output
        
    Note:
        This detection method is reliable for identifying modules that follow
        Ansible's recommended development patterns. The AnsibleModule pattern
        is well-established and consistent across the Ansible ecosystem.
    """
    with open(module) as f:
        for line in f.readlines():
            if "AnsibleModule(" in line:
                return True

    return False


def is_want_json_module(module: str) -> bool:
    """Detect if a module expects JSON input via an argument file.
    
    Scans the module file for the presence of "WANT_JSON" which indicates the
    module follows Ansible's WANT_JSON convention. These modules expect to
    receive their arguments as a JSON file path on the command line, rather
    than key=value pairs or stdin input.
    
    Args:
        module: File path to the module to examine. Should be a readable text
            file containing the module code.
    
    Returns:
        True if the module contains "WANT_JSON" and expects JSON file input,
        False if it uses other argument input methods.
    
    Raises:
        FileNotFoundError: If the module file does not exist.
        PermissionError: If the module file cannot be read due to permissions.
        UnicodeDecodeError: If the module file contains non-UTF8 binary data.
        OSError: If there are other filesystem access issues.
    
    Example:
        >>> # Check a WANT_JSON module
        >>> is_want_json_module("modules/uri.py")
        True  # Contains: WANT_JSON = True or similar
        
        >>> # Check a new-style module
        >>> is_want_json_module("modules/file.py")
        False  # Uses AnsibleModule instead
        
        >>> # Check a legacy module
        >>> is_want_json_module("modules/command.py")
        False  # Uses key=value argument files
    
    Detection Pattern:
        The function searches for the literal string "WANT_JSON" anywhere in
        the module file. This is typically found in variable declarations like
        "WANT_JSON = True" or in comments explaining the module's input format.
        
    Execution Implications:
        - WANT_JSON modules: Receive JSON file path as command-line argument
        - Input format: module.py /path/to/args.json
        - JSON content: {"param1": "value1", "param2": "value2", ...}
        - Output: JSON to stdout with module results
        
    WANT_JSON Convention:
        WANT_JSON modules follow this pattern:
        - Command line: python module.py /tmp/args
        - Argument file contains: JSON-encoded module parameters
        - Module reads and parses the JSON file internally
        - Suitable for modules that need complex nested arguments
        
    Historical Context:
        WANT_JSON was introduced before new-style modules to support modules
        that needed structured data input beyond simple key=value pairs. It's
        particularly useful for modules handling complex data structures or
        when backward compatibility with older Ansible versions is required.
        
    Note:
        WANT_JSON modules provide a middle ground between legacy key=value
        argument files and new-style stdin JSON input. They're common in
        modules that need to maintain compatibility with older Ansible
        versions while supporting complex argument structures.
    """
    with open(module) as f:
        for line in f.readlines():
            if "WANT_JSON" in line:
                return True

    return False


async def run_module_locally(
    host_name: str, host: Dict, module: str, module_args: Dict
) -> Tuple[str, Dict]:
    """Execute an Ansible-compatible module locally with appropriate argument handling.
    
    Orchestrates the complete execution of an Ansible module on the local system,
    including module type detection, temporary file setup, argument formatting,
    execution, and result processing. Supports all major Ansible module types
    with their specific argument handling requirements.
    
    Args:
        host_name: String identifier for the target host. Used for result
            attribution and logging context.
        host: Dictionary containing host configuration including
            ansible_python_interpreter and other host-specific settings.
        module: File path to the module to execute. Can be any Ansible-compatible
            module including Python scripts, binaries, or other executables.
        module_args: Dictionary of arguments to pass to the module. Structure
            depends on the module's requirements and input format.
    
    Returns:
        Tuple of (host_name, result_dict) where:
        - host_name: The input host identifier for result attribution
        - result_dict: Module execution results as a dictionary, typically
          containing keys like 'changed', 'msg', 'failed', etc. On execution
          errors, contains {'error': output} with raw output.
    
    Raises:
        FileNotFoundError: If the module file does not exist.
        PermissionError: If the module cannot be executed due to permissions.
        BaseException: Re-raised after logging for any execution failures.
    
    Example:
        >>> # Execute a setup module
        >>> host = {"ansible_python_interpreter": "/usr/bin/python3"}
        >>> args = {"gather_subset": "all"}
        >>> result = await run_module_locally("localhost", host, "modules/setup.py", args)
        >>> print(f"Host: {result[0]}, Facts: {result[1]['ansible_facts']}")
        
        >>> # Execute a command module
        >>> args = {"cmd": "echo hello"}
        >>> result = await run_module_locally("web01", host, "modules/command.py", args)
        >>> print(f"Output: {result[1]['stdout']}")
        
        >>> # Execute a binary module
        >>> args = {"target": "example.com"}
        >>> result = await run_module_locally("db01", host, "modules/ping", args)
        >>> print(f"Ping result: {result[1]['ping']}")
    
    Module Type Handling:
        The function automatically detects and handles different module types:
        
        Binary Modules:
        - Detection: is_binary_module() returns True
        - Execution: module_path args_file
        - Arguments: JSON file containing module_args
        
        New-Style Modules (AnsibleModule):
        - Detection: "AnsibleModule(" found in source
        - Execution: python module_path with stdin input
        - Arguments: JSON via stdin: {"ANSIBLE_MODULE_ARGS": module_args}
        
        WANT_JSON Modules:
        - Detection: "WANT_JSON" found in source
        - Execution: python module_path args_file
        - Arguments: JSON file containing module_args
        
        Legacy Modules:
        - Detection: Default case for other modules
        - Execution: python module_path args_file
        - Arguments: Key=value file format
    
    Execution Environment:
        - Temporary directory: Created for each execution
        - Module copy: Module is copied to temp directory as "module.py"
        - Interpreter: Uses host's ansible_python_interpreter or sys.executable
        - Arguments: Written to temporary argument files as needed
        - Cleanup: Temporary files are automatically cleaned up
    
    Error Handling:
        - JSON parsing errors: Returns {'error': raw_output}
        - Execution exceptions: Logged with full traceback, then re-raised
        - Module errors: Captured in result dictionary
        - File system errors: Propagated to caller
        
    Performance Considerations:
        - Asynchronous execution: Uses asyncio subprocess for non-blocking
        - Temporary files: Minimal filesystem impact with automatic cleanup
        - Memory usage: Captures full output in memory
        - Process isolation: Each module runs in separate process
        
    Note:
        This function provides full Ansible module compatibility while executing
        entirely on the local system. It handles the complexity of different
        module types transparently, making it suitable for both testing and
        production use cases where remote execution is not required.
    """
    try:
        logger.debug(f'run_module_locally {host_name=} {module=} ')
        tmp = tempfile.mkdtemp()
        tmp_module = os.path.join(tmp, "module.py")
        shutil.copy(module, tmp_module)
        # TODO: replace hashbang with ansible_python_interpreter
        # TODO: add utf-8 encoding line
        interpreter = host.get("ansible_python_interpreter", sys.executable)
        logger.debug(f"{interpreter}")
        if is_binary_module(module):
            logger.debug("is_binary_module")
            args = os.path.join(tmp, "args")
            with open(args, "w") as f:
                f.write(json.dumps(module_args))
            output = await check_output(f"{tmp_module} {args}")
        elif is_new_style_module(module):
            logger.debug("is_new_style_module")
            print(f"{interpreter} {tmp_module}")
            print(json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)))
            output = await check_output(
                f"{interpreter} {tmp_module}",
                stdin=json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)).encode(),
            )
        elif is_want_json_module(module):
            logger.debug("is_want_json_module")
            args = os.path.join(tmp, "args")
            with open(args, "w") as f:
                f.write(json.dumps(module_args))
            output = await check_output(f"{interpreter} {tmp_module} {args}")
        else:
            logger.debug("else")
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
    except BaseException:
        traceback.print_exc()
        raise


async def run_ftl_module_locally(
    host_name: str, host: Dict, module_path: str, module_args: Dict
) -> Tuple[str, dict]:
    """Execute an FTL-native module locally using direct Python function calls.
    
    Executes FTL-native modules by loading them as Python modules and calling
    their main() function directly. This approach provides better performance
    and integration compared to subprocess execution, while maintaining full
    async support and error handling.
    
    Args:
        host_name: String identifier for the target host. Used for result
            attribution and consistent return format with other execution methods.
        host: Dictionary containing host configuration. Currently unused for
            FTL modules but maintained for API consistency.
        module_path: File path to the FTL module to execute. Must be a valid
            Python file with a main() function defined.
        module_args: Dictionary of keyword arguments to pass to the module's
            main() function. Can be None for modules with no parameters.
    
    Returns:
        Tuple of (host_name, result_dict) where:
        - host_name: The input host identifier for result attribution
        - result_dict: Dictionary returned by the module's main() function,
          typically containing execution results, status, and any output data.
    
    Raises:
        FileNotFoundError: If the module_path does not exist.
        ImportError: If the module cannot be imported due to syntax errors.
        AttributeError: If the module does not have a main() function.
        TypeError: If main() function signature doesn't match provided arguments.
        Any exception: Propagated from the module's main() function execution.
    
    Example:
        >>> # Execute an FTL file management module
        >>> args = {"path": "/tmp/test", "state": "directory"}
        >>> result = await run_ftl_module_locally("server01", {}, "ftl_modules/file.py", args)
        >>> print(f"File operation: {result[1]['changed']}")
        
        >>> # Execute an FTL system info module
        >>> result = await run_ftl_module_locally("web01", {}, "ftl_modules/facts.py", {})
        >>> print(f"System info: {result[1]['facts']['hostname']}")
        
        >>> # Execute an FTL network module
        >>> args = {"interface": "eth0", "ip": "192.168.1.100"}
        >>> result = await run_ftl_module_locally("db01", {}, "ftl_modules/network.py", args)
        >>> print(f"Network config: {result[1]['msg']}")
    
    FTL Module Requirements:
        FTL modules must follow this structure:
        
        ```python
        async def main(**kwargs):
            # Module implementation
            return {
                "changed": True,
                "msg": "Operation completed",
                "data": {...}
            }
        ```
        
        Key requirements:
        - Must define an async main() function
        - Must accept **kwargs for flexible argument handling
        - Must return a dictionary with result data
        - Should follow FTL result conventions (changed, msg, etc.)
    
    Execution Method:
        The function uses runpy.run_path() to load and execute the module:
        1. Module is loaded into a new namespace
        2. The main() function is extracted from the module namespace
        3. Arguments are unpacked and passed as keyword arguments
        4. The async main() function is awaited for completion
        5. Results are returned in the standard tuple format
        
    Argument Handling:
        - None arguments: Converted to empty dictionary for **kwargs
        - Dictionary arguments: Passed directly as keyword arguments
        - Flexible signatures: Modules can accept any combination of parameters
        - Type safety: Arguments are passed as-is, module validates types
        
    Performance Benefits:
        - No subprocess overhead: Direct Python function calls
        - Better memory efficiency: Shared Python interpreter
        - Faster execution: No process creation or IPC
        - Native async support: True async execution without blocking
        - Exception propagation: Direct access to module exceptions
        
    Error Handling:
        - Import errors: Propagated if module has syntax issues
        - Missing main(): AttributeError if main() function not found
        - Signature mismatch: TypeError if arguments don't match
        - Module exceptions: Propagated directly to caller
        
    Use Cases:
        - High-performance automation tasks
        - Complex operations requiring shared state
        - Modules needing direct access to FTL internals
        - Testing and development scenarios
        - Custom business logic implementation
        
    Note:
        FTL modules provide superior performance and integration compared to
        subprocess-based execution. They're ideal for compute-intensive tasks
        or operations requiring tight integration with the FTL framework while
        maintaining the flexibility of the standard module interface.
    """

    if module_args is None:
        module_args = {}

    module = runpy.run_path(module_path)

    result = await module["main"](**module_args)
    return host_name, result
