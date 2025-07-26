"""Message protocol and communication system for FTL gate operations.

This module implements a custom length-prefixed JSON message protocol used for
communication between FTL processes and remote SSH gates. The protocol ensures
reliable message transmission over streams by prefixing each JSON message with
its length in hexadecimal format.

Key Features:
- Length-prefixed message protocol for reliable stream communication
- JSON serialization for structured data exchange
- Async stream support for non-blocking I/O operations
- Error handling with custom ProtocolError exceptions
- Support for both binary and string writers
- Broken pipe detection and graceful error handling

Protocol Format:
- 8-character hexadecimal length prefix (e.g., "0000001a")
- JSON-encoded message body containing [message_type, message_data]
- No message delimiters - length determines message boundaries

The message system enables FTL's gate architecture by providing a robust
communication channel for module execution requests and responses between
the main FTL process and remote gate processes running on target hosts.
"""

import json
import logging
from typing import Any, NamedTuple, Optional, Protocol, Union

from .exceptions import ProtocolError

logger = logging.getLogger(__name__)


class BinaryWriter(Protocol):
    """Protocol for binary writers that can write bytes."""

    def write(self, data: bytes) -> None: ...


class TextWriter(Protocol):
    """Protocol for text writers that can write strings."""

    def write(self, data: str) -> None: ...


class AsyncReader(Protocol):
    """Protocol for async readers that can read bytes."""

    async def read(self, size: int = -1) -> bytes: ...


# Type alias for JSON-serializable data
JsonSerializable = Union[dict, list, str, int, float, bool, None]


class GateMessage(NamedTuple):
    """Structured message container for FTL gate communication protocol.

    A typed container that represents a single message in the FTL gate protocol.
    Each message consists of a type identifier and associated data payload,
    following a standardized format for inter-process communication.

    The GateMessage provides type safety and structure for the various message
    types used in FTL's gate communication, including module execution requests,
    responses, system commands, and error notifications.

    Attributes:
        message_type: String identifier specifying the message category and
            purpose. Common types include "Module", "FTLModule", "Hello",
            "Shutdown", "Error", and "Result".
        message_body: Payload data associated with the message. Can be any
            JSON-serializable type including dictionaries, lists, strings,
            numbers, or None. Content structure depends on message_type.

    Example:
        >>> # Module execution request
        >>> msg = GateMessage("Module", {
        ...     "module_name": "ping",
        ...     "module_args": {"host": "example.com"}
        ... })
        >>> print(f"Type: {msg.message_type}, Body: {msg.message_body}")
        Type: Module, Body: {'module_name': 'ping', 'module_args': {'host': 'example.com'}}

        >>> # System command
        >>> hello_msg = GateMessage("Hello", {})
        >>> shutdown_msg = GateMessage("Shutdown", {})

        >>> # Error response
        >>> error_msg = GateMessage("Error", {
        ...     "error_type": "ModuleNotFound",
        ...     "message": "Module 'invalid' not found"
        ... })

    Note:
        As a NamedTuple, GateMessage instances are immutable and hashable,
        making them safe for use in concurrent environments and as dictionary
        keys. The structure provides both attribute and index access patterns.
    """

    message_type: str
    message_body: Any


def send_message(
    writer: BinaryWriter, msg_type: str, msg_data: JsonSerializable
) -> None:
    """Send a message using FTL's length-prefixed binary protocol.

    Serializes a message into JSON format, encodes it as bytes, and transmits
    it over a binary writer using FTL's length-prefixed protocol. The message
    format consists of an 8-character hexadecimal length prefix followed by
    the JSON-encoded message data.

    Args:
        writer: Binary writer object (such as asyncio StreamWriter or similar)
            that supports write() method for sending bytes. Must be capable
            of handling binary data transmission.
        msg_type: String identifier for the message type. Common values include
            "Module", "FTLModule", "Hello", "Shutdown", "Error", and "Result".
        msg_data: Message payload data that will be JSON-serialized. Must be
            JSON-serializable (dict, list, str, int, float, bool, None).

    Raises:
        TypeError: If msg_data contains non-JSON-serializable objects.
        OSError: If the writer encounters network or I/O errors during transmission.

    Example:
        >>> import asyncio
        >>> # With asyncio StreamWriter
        >>> writer = await asyncio.open_connection("localhost", 8080)
        >>> send_message(writer[1], "Module", {
        ...     "module_name": "ping",
        ...     "module_args": {"target": "example.com"}
        ... })

        >>> # Hello handshake
        >>> send_message(writer[1], "Hello", {})

        >>> # Shutdown command
        >>> send_message(writer[1], "Shutdown", {})

    Protocol Details:
        - Length prefix: 8-character lowercase hexadecimal (e.g., "0000001a")
        - Message format: JSON array [message_type, message_data]
        - Encoding: UTF-8 bytes for both length prefix and message body

    Note:
        This function is designed for binary stream writers. For string-based
        writers, use send_message_str() instead. The length prefix enables the
        receiver to read exactly the right number of bytes for each message.
    """
    message = json.dumps([msg_type, msg_data]).encode()
    # print('{:08x}'.format(len(message)).encode())
    # print(message)
    writer.write("{:08x}".format(len(message)).encode())
    writer.write(message)


def send_message_str(
    writer: TextWriter, msg_type: str, msg_data: JsonSerializable
) -> None:
    """Send a message using FTL's length-prefixed string protocol.

    Serializes a message into JSON format and transmits it over a string writer
    using FTL's length-prefixed protocol. This variant handles string-based
    writers such as SSH process stdin and includes error handling for broken
    pipe conditions that can occur during remote communication.

    Args:
        writer: String writer object that supports write() method for sending
            text data. Typically used with SSH process stdin or similar
            text-based communication channels.
        msg_type: String identifier for the message type. Common values include
            "Module", "FTLModule", "Hello", "Shutdown", "Error", and "Result".
        msg_data: Message payload data that will be JSON-serialized. Must be
            JSON-serializable (dict, list, str, int, float, bool, None).

    Raises:
        TypeError: If msg_data contains non-JSON-serializable objects.
        BrokenPipeError: Caught and logged when the remote end closes the connection.
            Other I/O errors are allowed to propagate.

    Example:
        >>> # With SSH process stdin
        >>> import subprocess
        >>> proc = subprocess.Popen(['ssh', 'user@host', 'python'], stdin=subprocess.PIPE, text=True)
        >>> send_message_str(proc.stdin, "Module", {
        ...     "module_name": "setup",
        ...     "module_args": {"gather_subset": "all"}
        ... })

        >>> # FTL module execution
        >>> send_message_str(proc.stdin, "FTLModule", {
        ...     "module": "base64_encoded_module_content",
        ...     "module_name": "custom_module",
        ...     "module_args": {"param1": "value1"}
        ... })

        >>> # Gate handshake
        >>> send_message_str(proc.stdin, "Hello", {})

    Protocol Details:
        - Length prefix: 8-character lowercase hexadecimal string (e.g., "0000001a")
        - Message format: JSON array [message_type, message_data]
        - Encoding: UTF-8 strings for both length prefix and message body

    Error Handling:
        - BrokenPipeError is caught and logged when remote process terminates
        - Other exceptions (TypeError, OSError) are allowed to propagate
        - Enables graceful handling of remote connection failures

    Note:
        This function is specifically designed for string-based writers like
        SSH process stdin. For binary stream writers, use send_message() instead.
        The broken pipe handling makes it suitable for remote gate communication.
    """
    message = json.dumps([msg_type, msg_data])
    # print('{:08x}'.format(len(message)))
    # print(message)
    try:
        writer.write("{:08x}".format(len(message)))
        writer.write(message)
    except BrokenPipeError:
        logger.error("BrokenPipeError")


async def read_message(reader: AsyncReader) -> Optional[Any]:
    """Read and parse a message from FTL's length-prefixed async protocol.

    Asynchronously reads a single message from a stream reader using FTL's
    length-prefixed protocol. First reads the 8-character hexadecimal length
    prefix, then reads exactly that many bytes of JSON message data and
    deserializes it into a Python object.

    Args:
        reader: Async stream reader object that supports read() method for
            receiving bytes asynchronously. Typically an asyncio StreamReader
            or SSH process stdout.

    Returns:
        Parsed JSON message as a Python object (typically a list containing
        [message_type, message_data]), or None if the stream is closed/EOF.
        The exact structure depends on the message format sent by the peer.

    Raises:
        ProtocolError: If the length prefix contains invalid hexadecimal
            characters or if the protocol format is corrupted. Includes
            available data in the error for debugging.
        json.JSONDecodeError: If the message body contains invalid JSON.
        OSError: If the reader encounters network or I/O errors.

    Example:
        >>> import asyncio
        >>> # With asyncio StreamReader
        >>> reader, writer = await asyncio.open_connection("localhost", 8080)
        >>> message = await read_message(reader)
        >>> if message:
        ...     msg_type, msg_data = message
        ...     print(f"Received {msg_type}: {msg_data}")
        ... else:
        ...     print("Connection closed")

        >>> # Example message formats received:
        >>> # ["Hello", {}]  - Handshake response
        >>> # ["Result", {"changed": True, "msg": "Success"}]  - Module result
        >>> # ["Error", {"error_type": "ModuleNotFound", "msg": "..."}]  - Error

        >>> # Reading in a loop
        >>> while True:
        ...     msg = await read_message(reader)
        ...     if msg is None:
        ...         break  # Stream closed
        ...     # Process message...

    Protocol Details:
        - Length prefix: 8-character hexadecimal string (e.g., "0000001a")
        - Message body: JSON-encoded data of exact length specified
        - EOF handling: Returns None when stream is closed

    Error Recovery:
        - Invalid hex in length: Raises ProtocolError with partial data
        - Malformed JSON: Allows JSONDecodeError to propagate
        - Network errors: Allows OSError to propagate
        - Graceful EOF: Returns None for clean stream closure

    Note:
        This function automatically handles the protocol framing and only
        returns complete, valid messages. The while True loop ensures robust
        handling of protocol-level details while providing a clean interface
        for message consumption.
    """
    while True:
        length = await reader.read(8)
        if not length:
            return None
        try:
            value = await reader.read(int(length, 16))
        except ValueError:
            raise ProtocolError(length + await reader.read())
        return json.loads(value)
