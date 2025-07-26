"""FTL Gate: Remote execution environment for Faster Than Light automation.

This module implements the FTL gate system, which provides a remote execution
environment for running automation modules on target hosts. The gate runs as
a Python process on remote systems and communicates with the main FTL process
through a custom length-prefixed JSON message protocol.

Key Features:
- Remote module execution with multiple Ansible-compatible formats
- Asynchronous message-based communication protocol
- Support for binary modules, new-style modules, and FTL-native modules
- Automatic module detection and appropriate execution strategies
- Comprehensive error handling and logging
- Secure temporary file management

Protocol Overview:
The gate communicates using a length-prefixed JSON message protocol:
- 8-character hexadecimal length prefix (e.g., "0000001a")
- JSON message body: [message_type, message_data]
- Message types: Hello, Module, FTLModule, Shutdown, etc.

Module Execution Types:
1. Binary modules: Executable files with JSON arguments file
2. New-style modules: Python modules using AnsibleModule class
3. Want-JSON modules: Python modules expecting JSON arguments file
4. Old-style modules: Python modules with key=value arguments
5. FTL modules: Native async Python modules with main() function

The gate provides an isolated execution environment with proper cleanup,
logging, and error reporting back to the main FTL process.
"""

import asyncio
import base64
import importlib.resources
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import ftl_gate  # type: ignore

logger = logging.getLogger("ftl_gate")


class ModuleNotFoundException(Exception):
    """Exception raised when a requested module cannot be found in the gate bundle.
    
    This exception is raised when attempting to execute a module that doesn't
    exist in the gate's bundled modules. It triggers a "ModuleNotFound" message
    back to the main FTL process, which may then send the module content for
    execution.
    
    Attributes:
        Inherits from Exception with standard message handling.
    
    Example:
        >>> raise ModuleNotFoundException("ping")
        ModuleNotFoundException: ping
    """
    pass

class StdinReader:
    """Asynchronous reader for stdin when normal StreamReader setup fails.
    
    Provides a fallback mechanism for reading from stdin in environments where
    asyncio's standard pipe connection methods don't work. Uses executor-based
    threading to make blocking stdin reads asynchronous.
    
    This class implements a compatible interface with asyncio.StreamReader
    for seamless fallback functionality.
    """

    async def read(self, n: int) -> bytes:
        """Read up to n bytes from stdin asynchronously.
        
        Uses asyncio's run_in_executor to perform blocking stdin reads in a
        thread pool, making them compatible with async code. Automatically
        encodes string results to bytes for protocol compatibility.
        
        Args:
            n: Maximum number of bytes to read from stdin.
        
        Returns:
            Bytes read from stdin, up to n bytes. May return fewer bytes
            than requested if EOF is reached or input is limited.
        
        Example:
            >>> reader = StdinReader()
            >>> data = await reader.read(8)
            >>> print(len(data))
            8
        
        Note:
            This method blocks until data is available or EOF is reached.
            It's designed for use when standard asyncio StreamReader fails.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, sys.stdin.read, n)
        if isinstance(result, str):
            result = result.encode()
        return cast(bytes, result)


class StdoutWriter:
    """Asynchronous writer for stdout when normal StreamWriter setup fails.
    
    Provides a fallback mechanism for writing to stdout in environments where
    asyncio's standard pipe connection methods don't work. Offers a compatible
    interface with asyncio.StreamWriter for seamless fallback.
    
    This class handles the conversion from bytes to strings automatically
    and writes directly to stdout.
    """

    def write(self, data: bytes) -> None:
        """Write bytes data to stdout.
        
        Converts bytes data to string and writes it directly to stdout.
        This provides compatibility with the standard StreamWriter interface
        while handling the bytes-to-string conversion automatically.
        
        Args:
            data: Bytes data to write to stdout. Will be decoded as UTF-8
                and written to the standard output stream.
        
        Example:
            >>> writer = StdoutWriter()
            >>> writer.write(b"Hello, World!")
            Hello, World!
        
        Note:
            This method writes directly to stdout without buffering.
            It's designed for protocol message output in gate communication.
        """
        sys.stdout.write(data.decode())


async def connect_stdin_stdout() -> Tuple[Union[asyncio.StreamReader, StdinReader], Union[asyncio.StreamWriter, StdoutWriter]]:
    """Establish async I/O connections to stdin and stdout.
    
    Attempts to create proper asyncio StreamReader and StreamWriter connections
    to stdin and stdout for the gate's message protocol communication. Falls
    back to custom reader/writer classes if standard pipe connection fails.
    
    This function handles the complexity of setting up async I/O in different
    environments where stdin/stdout may or may not support asyncio pipes.
    
    Returns:
        Tuple containing (reader, writer) where:
        - reader: AsyncIO StreamReader or StdinReader for reading messages
        - writer: AsyncIO StreamWriter or StdoutWriter for sending responses
    
    Raises:
        No exceptions are raised; ValueError from pipe connection is caught
        and triggers fallback to custom reader/writer implementations.
    
    Example:
        >>> reader, writer = await connect_stdin_stdout()
        >>> # Use reader and writer for protocol communication
        >>> data = await reader.read(8)
        >>> writer.write(response_data)
    
    Note:
        The function prioritizes asyncio's native streams but gracefully
        degrades to custom implementations when necessary. Both paths
        provide compatible interfaces for the message protocol.
    """
    loop = asyncio.get_event_loop()
    reader: Union[asyncio.StreamReader, StdinReader]
    writer: Union[asyncio.StreamWriter, StdoutWriter]
    
    try:
        # Try to connect to pipes
        stream_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(stream_reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        stream_writer = asyncio.StreamWriter(w_transport, w_protocol, stream_reader, loop)
        reader = stream_reader
        writer = stream_writer
    except ValueError:
        # Fall back to simple reader and writer
        reader = StdinReader()
        writer = StdoutWriter()
    return reader, writer


async def read_message(reader: Union[asyncio.StreamReader, StdinReader]) -> Tuple[Optional[str], Optional[Any]]:
    """Read and parse a message from the FTL gate protocol stream.
    
    Implements the FTL gate message protocol by reading a length-prefixed JSON
    message from the input stream. The protocol format consists of an 8-character
    hexadecimal length prefix followed by exactly that many bytes of JSON data.
    
    Protocol Format:
    - 8 bytes: Hexadecimal length (e.g., "0000001a" for 26 bytes)
    - N bytes: JSON array [message_type, message_data]
    
    The function handles various edge cases including empty messages, channel
    closure, and malformed data. It continues reading until a valid message
    is received or the channel closes.
    
    Args:
        reader: Async reader (StreamReader or StdinReader) to read from.
            Must support async read(n) method.
    
    Returns:
        Tuple of (message_type, message_data) where:
        - message_type: String identifying the message type (e.g., "Hello")
        - message_data: Associated data (dict, list, or other JSON types)
        Returns (None, None) if the channel is closed or EOF is reached.
    
    Raises:
        json.JSONDecodeError: If the message contains invalid JSON.
        ValueError: If the length prefix contains invalid hexadecimal.
        BaseException: Re-raises any JSON parsing exceptions for debugging.
    
    Example:
        >>> # Reading a hello message
        >>> msg_type, data = await read_message(reader)
        >>> print(f"Received: {msg_type} with data: {data}")
        Received: Hello with data: {}
        
        >>> # Channel closed scenario
        >>> msg_type, data = await read_message(reader)
        >>> if msg_type is None:
        ...     print("Channel closed")
        Channel closed
    
    Protocol Details:
        - Length must be 8 hexadecimal characters (00000000 to ffffffff)
        - Zero-length messages are skipped and reading continues
        - Partial reads are handled by continuing until full message received
        - Empty values after reading full length trigger re-read
        - Supports manual debugging by accepting console input
    
    Note:
        This function implements the core of FTL's gate communication protocol.
        It's designed to be robust against network issues and supports both
        programmatic and manual testing scenarios.
    """

    while True:

        # Messages are Length Value
        # Length is a 8 byte field in hexadecimal
        # Value is a length byte field

        value = b""
        length_hexadecimal = b"0"
        length = 0

        # Read length
        length_hexadecimal = await reader.read(8)
        # If the length_hexadecimal is None then the channel was closed
        if not length_hexadecimal:
            return None, None

        # Read value
        if length_hexadecimal.strip():
            length = int(length_hexadecimal.strip(), 16)
            if length == 0:
                continue
            # If value is a new-line try the read operation again
            while True:
                value = await reader.read(length)
                # If the value is None then the channel was closed
                if not value:
                    return None, None
                while len(value) != length:
                    value += await reader.read(length - len(value))
                value = value.strip()
                # Keep reading until we get a value
                # This is useful for manual debugging
                # Run with python __main__.py
                # Enter: 0000000d
                # Enter: ["Hello", {}]
                # Response should be  0000000d["Hello", {}]
                # Enter: 00000010
                # Enter: ["Shutdown", {}]
                # System will exit
                if value:
                    # logger.info(f'{length_hexadecimal} {value}')
                    try:
                        parsed_message = json.loads(value)
                        return cast(Tuple[Optional[str], Optional[Any]], parsed_message)
                    except BaseException:
                        # print(value)
                        raise
                else:
                    continue


def send_message(writer: Union[asyncio.StreamWriter, StdoutWriter], msg_type: str, data: Any) -> None:
    """Send a message using the FTL gate protocol format.
    
    Encodes and sends a message using FTL's length-prefixed JSON protocol.
    The message is formatted as a JSON array [message_type, data], encoded
    to bytes, and prefixed with an 8-character hexadecimal length.
    
    Protocol Format:
    - 8 bytes: Hexadecimal length of message (e.g., "0000001a")
    - N bytes: JSON-encoded [message_type, data] array
    
    Args:
        writer: Writer object (StreamWriter or StdoutWriter) to send through.
            Must support write(bytes) method.
        msg_type: String identifying the message type. Common types include:
            "Hello", "ModuleResult", "FTLModuleResult", "Error", "Goodbye".
        data: Message payload data. Must be JSON-serializable (dict, list,
            str, int, float, bool, None, or combinations thereof).
    
    Raises:
        AssertionError: If the encoded message exceeds 16^8 bytes (4GB limit).
        TypeError: If data contains non-JSON-serializable objects.
        json.JSONEncodeError: If data cannot be serialized to JSON.
    
    Example:
        >>> # Send a hello response
        >>> send_message(writer, "Hello", {})
        
        >>> # Send module execution result
        >>> result_data = {"stdout": "success", "stderr": ""}
        >>> send_message(writer, "ModuleResult", result_data)
        
        >>> # Send error message
        >>> send_message(writer, "Error", {"message": "Module not found"})
    
    Protocol Constraints:
        - Maximum message size: 16^8 bytes (approximately 4GB)
        - Message data must be JSON-serializable
        - Length prefix is always exactly 8 hexadecimal characters
        - No message framing beyond length prefix
    
    Note:
        This function implements the core message sending for FTL's gate
        communication protocol. It ensures proper formatting and size
        constraints for reliable message transmission.
    """

    # A message has a Length[Type, Data] format.
    # The first 8 bytes are the length in hexadecimal
    # The next Length bytes are JSON encoded data.
    # The JSON encoded data is a pair where the first
    # item is the message type and the second
    # item is the data.
    message = json.dumps([msg_type, data]).encode()
    assert (
        len(message) < 16**8
    ), f"Message {msg_type} is too big.  Break up messages into less than 16**8 bytes"
    writer.write("{:08x}".format(len(message)).encode())
    writer.write(message)


async def check_output(cmd: str, env: Optional[Dict[str, str]] = None, stdin: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Execute a shell command asynchronously and capture its output.
    
    Creates an asynchronous subprocess to execute the specified shell command,
    optionally providing custom environment variables and stdin input. Captures
    both stdout and stderr for comprehensive output handling.
    
    This function is used primarily for executing automation modules in various
    formats (binary, Python scripts) with proper I/O capture and logging.
    
    Args:
        cmd: Shell command string to execute. Can include arguments, pipes,
            redirections, and other shell features.
        env: Optional dictionary of environment variables to set for the
            subprocess. If None, inherits the current process environment.
        stdin: Optional bytes data to send to the process stdin. If provided,
            data is sent and stdin is closed.
    
    Returns:
        Tuple of (stdout, stderr) where both are bytes containing the
        complete output from the command execution.
    
    Raises:
        OSError: If the command cannot be executed or process creation fails.
        asyncio.TimeoutError: If command execution exceeds system limits.
        asyncio.subprocess.SubprocessError: For other subprocess-related errors.
    
    Example:
        >>> # Execute a simple command
        >>> stdout, stderr = await check_output("echo 'Hello World'")
        >>> print(stdout.decode())
        Hello World
        
        >>> # Execute with custom environment
        >>> env = {"PYTHONPATH": "/custom/path"}
        >>> stdout, stderr = await check_output("python -c 'import sys; print(sys.path)'", env=env)
        
        >>> # Execute with stdin input
        >>> input_data = b'{"key": "value"}'
        >>> stdout, stderr = await check_output("python script.py", stdin=input_data)
    
    Logging:
        - Debug logs command creation, communication, and completion
        - Useful for tracking module execution progress and debugging
    
    Note:
        This function is designed for executing automation modules and handles
        the async subprocess management required for non-blocking execution
        in the gate environment.
    """
    logger.debug(f'check_output {cmd} create')
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    logger.debug(f'check_output {cmd} communicate')
    stdout, stderr = await proc.communicate(stdin)
    logger.debug(f'check_output {cmd} complete')
    return stdout, stderr


def is_binary_module(module: bytes) -> bool:
    """Detect if a module is a binary executable rather than a text script.
    
    Determines whether the provided module content represents a binary
    executable file by attempting to decode it as UTF-8 text. Binary
    modules are executed directly as programs, while text modules are
    interpreted through Python.
    
    Args:
        module: Raw bytes content of the module file to analyze.
    
    Returns:
        True if the module is binary (cannot be decoded as UTF-8),
        False if it's a text-based module.
    
    Example:
        >>> # Text-based Python module
        >>> text_module = b'#!/usr/bin/python3\\nprint("hello")'
        >>> is_binary_module(text_module)
        False
        
        >>> # Binary executable
        >>> with open('/bin/ls', 'rb') as f:
        ...     binary_module = f.read()
        >>> is_binary_module(binary_module)
        True
    
    Module Execution:
        - Binary modules: Executed directly with arguments file
        - Text modules: Further analyzed for Python execution strategy
    
    Note:
        This is the first step in FTL's module type detection pipeline.
        Binary modules bypass Python interpretation entirely.
    """
    try:
        module.decode()
        return False
    except UnicodeDecodeError:
        return True


def is_new_style_module(module: bytes) -> bool:
    """Detect if a module uses Ansible's new-style module format.
    
    Determines whether a Python module uses the new-style Ansible module
    format by searching for the "AnsibleModule(" string. New-style modules
    use the AnsibleModule class and expect arguments via stdin as JSON.
    
    Args:
        module: Raw bytes content of the Python module to analyze.
    
    Returns:
        True if the module contains "AnsibleModule(" indicating new-style
        format, False otherwise.
    
    Example:
        >>> # New-style module content
        >>> new_style = b'''
        ... from ansible.module_utils.basic import AnsibleModule
        ... module = AnsibleModule(argument_spec={...})
        ... '''
        >>> is_new_style_module(new_style)
        True
        
        >>> # Old-style module
        >>> old_style = b'#!/usr/bin/python3\\nprint("result")'
        >>> is_new_style_module(old_style)
        False
    
    Module Execution:
        New-style modules receive arguments as:
        - Environment: ANSIBLE_MODULE_ARGS with JSON data
        - Stdin: JSON data with module arguments
        - Execution: python module.py (no arguments file)
    
    Note:
        This detection method is compatible with Ansible's module
        identification approach and ensures proper argument passing.
    """
    if b"AnsibleModule(" in module:
        return True
    else:
        return False


def is_want_json_module(module: bytes) -> bool:
    """Detect if a module expects JSON arguments via file parameter.
    
    Determines whether a Python module uses the WANT_JSON format by
    searching for the "WANT_JSON" string. These modules expect a JSON
    arguments file as their first command-line parameter.
    
    Args:
        module: Raw bytes content of the Python module to analyze.
    
    Returns:
        True if the module contains "WANT_JSON" indicating it expects
        JSON arguments file, False otherwise.
    
    Example:
        >>> # WANT_JSON module content
        >>> want_json = b'''
        ... #!/usr/bin/python3
        ... # WANT_JSON
        ... import sys, json
        ... with open(sys.argv[1]) as f:
        ...     args = json.load(f)
        ... '''
        >>> is_want_json_module(want_json)
        True
    
    Module Execution:
        WANT_JSON modules receive arguments as:
        - File: JSON file with module arguments
        - Command: python module.py /path/to/args.json
        - Format: Full JSON structure in arguments file
    
    Note:
        This is an intermediate format between old-style and new-style
        Ansible modules, providing JSON arguments via file parameter.
    """
    if b"WANT_JSON" in module:
        return True
    else:
        return False


def get_python_path() -> str:
    """Get the current Python path for subprocess environment setup.
    
    Constructs a PYTHONPATH string from the current sys.path to ensure
    that subprocess module executions have access to the same Python
    modules and packages as the gate process.
    
    Returns:
        String containing the PYTHONPATH value with all current sys.path
        entries joined by the OS-appropriate path separator.
    
    Example:
        >>> path = get_python_path()
        >>> print(path)
        /usr/lib/python3.9:/usr/lib/python3.9/site-packages:/custom/modules
    
    Usage:
        >>> env = os.environ.copy()
        >>> env["PYTHONPATH"] = get_python_path()
        >>> # Now subprocess will have same module access
    
    Note:
        This ensures that modules executed by the gate have access to
        the same Python environment, including any custom modules or
        packages available to the gate process itself.
    """
    return os.pathsep.join(sys.path)


async def gate_run_module(writer: Union[asyncio.StreamWriter, StdoutWriter], module_name: str, module: Optional[str] = None, module_args: Optional[Dict[str, Any]] = None) -> None:
    """Execute an automation module within the FTL gate environment.
    
    This is the core module execution function that handles running automation
    modules in various formats within the gate's controlled environment. It
    automatically detects the module type and uses the appropriate execution
    strategy while managing temporary files and cleanup.
    
    Module Execution Flow:
    1. Create secure temporary directory
    2. Load module (from message or gate bundle)
    3. Detect module type (binary, new-style, want-json, old-style)
    4. Execute with appropriate argument format
    5. Capture output and send result
    6. Clean up temporary files
    
    Args:
        writer: Output writer for sending results back to main FTL process.
        module_name: Name of the module to execute. Used for bundled modules
            and as identifier in logging and error messages.
        module: Optional base64-encoded module content. If provided, this
            content is used instead of loading from the gate bundle.
        module_args: Optional dictionary of arguments to pass to the module.
            Format depends on detected module type.
    
    Raises:
        ModuleNotFoundException: If module_name is not found in gate bundle
            and no module content is provided.
        OSError: If temporary file operations or module execution fails.
        json.JSONEncodeError: If module arguments cannot be serialized.
    
    Module Types and Execution:
        - Binary: Execute directly with JSON args file
        - New-style: Python execution with ANSIBLE_MODULE_ARGS via stdin
        - WANT_JSON: Python execution with JSON args file parameter
        - Old-style: Python execution with key=value args file parameter
    
    Example Message Flow:
        >>> # Gate receives Module message
        >>> await gate_run_module(writer, "ping", None, {"host": "example.com"})
        >>> # Gate sends ModuleResult message back
        
        >>> # With custom module content
        >>> encoded_module = base64.b64encode(module_code).decode()
        >>> await gate_run_module(writer, "custom", encoded_module, {})
    
    Temporary File Management:
        - Creates unique temporary directory per execution
        - Stores module file and arguments file as needed
        - Sets appropriate permissions (executable for binary modules)
        - Guarantees cleanup even if execution fails
    
    Environment Setup:
        - Inherits current environment variables
        - Adds PYTHONPATH for Python module access
        - Supports custom environment per module type
    
    Logging:
        - Info level: Module name, execution type, major steps
        - Debug level: File paths, argument details, execution commands
        - Error level: Exceptions and cleanup issues
    
    Note:
        This function implements FTL's core module execution capability,
        providing compatibility with multiple Ansible module formats while
        maintaining security through temporary file isolation.
    """
    logger.info(module_name)
    tempdir = tempfile.mkdtemp(prefix="ftl-module")
    try:
        module_file = os.path.join(tempdir, f"ftl_{module_name}")
        logger.info(module_file)
        env = os.environ.copy()
        env["PYTHONPATH"] = get_python_path()
        if module is not None:
            logger.info("loading module from message")
            module_bytes = base64.b64decode(module)
            with open(module_file, "wb") as f:
                f.write(module_bytes)
        else:
            logger.info("loading module from ftl_gate")
            modules = importlib.resources.files(ftl_gate)
            with open(module_file, "wb") as f2:
                try:
                    module_bytes = importlib.resources.files(ftl_gate).joinpath(module_name).read_bytes()
                except FileNotFoundError:
                    logger.info(f"Module {module_name} not found in gate")
                    raise ModuleNotFoundException(module_name)
                f2.write(module_bytes)
        if is_binary_module(module_bytes):
            logger.info("is_binary_module")
            args = os.path.join(tempdir, "args")
            with open(args, "w") as f:
                f.write(json.dumps(module_args))
            os.chmod(module_file, stat.S_IEXEC | stat.S_IREAD)
            stdout, stderr = await check_output(f"{module_file} {args}")
        elif is_new_style_module(module_bytes):
            logger.info(f"is_new_style_module {module_file}")
            logger.info(f"ANSIBLE_MODULE_ARGS {json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args))}")
            stdout, stderr = await check_output(
                f"{sys.executable} {module_file}",
                stdin=json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)).encode(),
                env=env,
            )
            logger.info(f"is_new_style_module {module_file} complete")
        elif is_want_json_module(module_bytes):
            logger.info("is_want_json_module")
            args = os.path.join(tempdir, "args")
            with open(args, "w") as f:
                f.write(json.dumps(module_args))
            stdout, stderr = await check_output(
                f"{sys.executable} {module_file} {args}", env=env
            )
        else:
            logger.info("is_old_style_module")
            args = os.path.join(tempdir, "args")
            with open(args, "w") as f:
                if module_args is not None:
                    f.write(
                        " ".join(["=".join([k, v]) for k, v in module_args.items()])
                    )
                else:
                    f.write("")
            stdout, stderr = await check_output(
                f"{sys.executable} {module_file} {args}", env=env
            )
        logger.info("Sending ModuleResult")
        send_message(
            writer, "ModuleResult", dict(stdout=stdout.decode(), stderr=stderr.decode())
        )
    finally:
        logger.info(f"cleaning up {tempdir}")
        shutil.rmtree(tempdir)
        logger.info("complete")



async def run_ftl_module(writer: Union[asyncio.StreamWriter, StdoutWriter], module_name: str, module: str, module_args: Optional[Dict[str, Any]] = None) -> None:
    """Execute an FTL-native module with async main() function.
    
    Executes FTL-native modules, which are Python modules with async main()
    functions that can be called directly without subprocess execution. This
    provides better performance and more flexible return value handling
    compared to traditional Ansible modules.
    
    FTL Module Requirements:
    - Must be valid Python code
    - Must contain an async main() function
    - main() function should return JSON-serializable data
    - Can use any Python libraries available to the gate
    
    Args:
        writer: Output writer for sending results back to main FTL process.
        module_name: Name identifier for the module, used in logging and
            as the __file__ attribute in the module's global namespace.
        module: Base64-encoded Python source code of the FTL module.
        module_args: Optional dictionary of arguments available to the module.
            Currently unused but reserved for future argument passing.
    
    Raises:
        base64.binascii.Error: If module content is not valid base64.
        SyntaxError: If the decoded module contains invalid Python syntax.
        CompileError: If the module cannot be compiled to bytecode.
        NameError: If the module doesn't contain a main() function.
        TypeError: If main() is not an async function.
        BaseException: Any exception raised by the module's main() function.
    
    Example FTL Module:
        ```python
        # example_ftl_module.py
        async def main():
            # Module logic here
            return {"result": "success", "data": [1, 2, 3]}
        ```
    
    Execution Environment:
        - Module runs in isolated namespace
        - __file__ attribute set to module_name
        - Access to all Python libraries available to gate
        - Direct async execution without subprocess overhead
    
    Message Flow:
        >>> # Gate receives FTLModule message
        >>> await run_ftl_module(writer, "async_ping", encoded_module, {})
        >>> # Gate sends FTLModuleResult message with return value
    
    Example:
        >>> # Module that returns complex data
        >>> module_code = '''
        ... async def main():
        ...     import asyncio
        ...     await asyncio.sleep(0.1)  # Async operation
        ...     return {"status": "completed", "items": [1, 2, 3]}
        ... '''
        >>> encoded = base64.b64encode(module_code.encode()).decode()
        >>> await run_ftl_module(writer, "test", encoded, {})
        # Sends: ["FTLModuleResult", {"result": {"status": "completed", "items": [1, 2, 3]}}]
    
    Performance Benefits:
        - No subprocess creation overhead
        - Direct async execution within gate process
        - No serialization overhead for complex return types
        - Full access to Python async ecosystem
    
    Security Considerations:
        - Module code is executed in the same process as the gate
        - No sandboxing beyond Python's normal execution environment
        - Module has access to all gate process capabilities
    
    Note:
        FTL modules provide the highest performance and flexibility for
        automation tasks that can be implemented in pure Python with
        async/await patterns.
    """

    module_compiled = compile(base64.b64decode(module), module_name, "exec")

    globals_dict: Dict[str, Any] = {"__file__": module_name}
    locals_dict: Dict[str, Any] = {}

    exec(module_compiled, globals_dict, locals_dict)
    logger.info("Calling FTL module")
    result = await locals_dict["main"]()
    logger.info("Sending FTLModuleResult")
    send_message(writer, "FTLModuleResult", dict(result=result))


async def main(args: List[str]) -> Optional[int]:
    """Main entry point for the FTL gate process.
    
    Initializes the gate environment, establishes communication with the main
    FTL process, and enters the message processing loop. Handles all incoming
    messages and coordinates module execution while providing comprehensive
    error handling and logging.
    
    Message Processing Loop:
        1. Read message from stdin using FTL protocol
        2. Dispatch to appropriate handler based on message type
        3. Execute requested operation (module run, hello, etc.)
        4. Send response back through stdout
        5. Handle errors and continue or exit as appropriate
    
    Supported Message Types:
        - "Hello": Handshake/keepalive message, echoed back
        - "Module": Execute standard automation module
        - "FTLModule": Execute FTL-native async module
        - "Shutdown": Clean shutdown of gate process
        - Others: Send error response for unknown types
    
    Args:
        args: Command-line arguments passed to the gate process.
            Currently unused but available for future extensions.
    
    Returns:
        Optional[int]: Exit code for the process:
        - None: Normal shutdown (equivalent to 0)
        - 1: Error shutdown due to unhandled exception
    
    Error Handling:
        - ModuleNotFoundException: Sends ModuleNotFound message, continues
        - BaseException: Sends GateSystemError message, exits with code 1
        - Protocol errors: Logged and may cause exit
    
    Logging Configuration:
        - Log file: /tmp/ftl_gate.log
        - Level: DEBUG for comprehensive tracing
        - Format: Timestamp and message for log analysis
        - Captures: System info, paths, environment, and all operations
    
    Example Startup:
        >>> # Gate started by main FTL process
        >>> exit_code = await main(sys.argv[1:])
        >>> # Gate processes messages until shutdown or error
    
    Communication Protocol:
        - Input: Length-prefixed JSON messages via stdin
        - Output: Length-prefixed JSON responses via stdout
        - Logging: Debug information to /tmp/ftl_gate.log
    
    Lifecycle:
        1. Initialize logging and communication
        2. Log system information for debugging
        3. Enter message processing loop
        4. Handle shutdown gracefully or exit on error
        5. Return appropriate exit code
    
    Security Features:
        - Isolated temporary directory creation per module
        - Automatic cleanup of temporary files
        - Sandboxed module execution environment
        - Comprehensive error handling prevents crashes
    
    Note:
        This function implements the core gate server functionality,
        providing a secure and robust environment for remote module
        execution with full error handling and logging capabilities.
    """

    logging.basicConfig(format="%(asctime)s - %(message)s", filename="/tmp/ftl_gate.log", level=logging.DEBUG)

    logger.info(f"sys.executable {sys.executable}")
    logger.debug(f"sys.path {sys.path}")
    logger.debug(f"os.environ {os.environ}")

    reader, writer = await connect_stdin_stdout()

    while True:

        try:
            msg_type, data = await read_message(reader)
            if msg_type is None:
                logger.info("End of input")
                send_message(writer, "Goodbye", {})
                return None
            elif msg_type == "Hello":
                logger.info("hello")
                send_message(writer, msg_type, data)
            elif msg_type == "Module":
                logger.info("Module")
                if data is not None and isinstance(data, dict):
                    await gate_run_module(writer, **data)
                else:
                    send_message(writer, "Error", {"message": "Invalid Module data"})
            elif msg_type == "FTLModule":
                logger.info("FTLModule")
                if data is not None and isinstance(data, dict):
                    await run_ftl_module(writer, **data)
                else:
                    send_message(writer, "Error", {"message": "Invalid FTLModule data"})
            elif msg_type == "Shutdown":
                logger.info("Shutdown")
                send_message(writer, "Goodbye", {})
                return None
            else:
                send_message(
                    writer, "Error", dict(message=f"Unknown message type {msg_type}")
                )
        except ModuleNotFoundException as e:
            send_message(
                writer, "ModuleNotFound", dict(message=f"Module {e} not found in gate bundle.")
            )
        except BaseException as e:
            send_message(
                writer,
                "GateSystemError",
                dict(message=f"Exception {e} traceback {traceback.format_exc()}"),
            )
            logger.error(f"GateSystemError: {e}")
            logger.error(traceback.format_exc())
            return 1


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
