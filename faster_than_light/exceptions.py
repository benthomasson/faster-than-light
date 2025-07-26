"""Custom exception classes for FTL automation framework.

This module defines FTL-specific exception classes that provide clear, semantic
error handling throughout the automation framework. These exceptions enable
precise error identification and appropriate handling strategies for different
failure scenarios encountered during automation execution.

Key Benefits:
- Semantic error identification for different failure types
- Clear separation between FTL-specific and general Python errors
- Improved error handling and debugging capabilities
- Consistent error reporting across the framework
- Enhanced user experience with meaningful error messages

Exception Hierarchy:
- ModuleNotFound: Raised when automation modules cannot be located
- ProtocolError: Raised when communication protocol issues occur

The custom exceptions follow Python's standard exception conventions while
providing domain-specific context for FTL automation scenarios. They enable
calling code to implement appropriate error handling strategies based on the
specific type of failure encountered.

Integration:
These exceptions are used throughout the FTL framework for consistent error
handling in module discovery, gate communication, remote execution, and other
core automation operations. They provide a clean interface for error handling
and enable robust automation workflows with proper failure recovery.
"""


class ModuleNotFound(Exception):
    """Exception raised when an automation module cannot be found or loaded.

    This exception is raised when FTL's module discovery system cannot locate
    a requested automation module in the configured module directories. It
    indicates that the module name provided does not correspond to any
    discoverable module file in the search paths.

    Common Scenarios:
        - Module name typos or incorrect spelling
        - Module not present in any configured module directory
        - Module file permissions preventing access
        - Module directory paths misconfigured or inaccessible
        - Module name conflicts or ambiguous module resolution

    Usage Context:
        This exception is typically raised by:
        - find_module() in util.py when module discovery fails
        - build_ftl_gate() in gate.py when required modules are missing
        - Module loading operations in various execution contexts

    Handling Strategies:
        - Verify module name spelling and case sensitivity
        - Check module directory configuration and accessibility
        - Ensure module files exist and have proper permissions
        - Review module search path priorities and conflicts
        - Implement fallback modules or graceful degradation

    Example:
        >>> from faster_than_light.exceptions import ModuleNotFound
        >>> try:
        ...     module_path = find_module(["./modules"], "nonexistent_module")
        ... except ModuleNotFound as e:
        ...     print(f"Module not found: {e}")
        ...     # Handle missing module - use default, prompt user, etc.
        Module not found: Module nonexistent_module not found in ['./modules']

        >>> # In gate building context
        >>> try:
        ...     gate_path, gate_hash = build_ftl_gate(
        ...         modules=["missing_module"],
        ...         module_dirs=["./modules"]
        ...     )
        ... except ModuleNotFound as e:
        ...     print(f"Cannot build gate: {e}")
        ...     # Handle by building gate without the missing module
        Cannot build gate: Cannot find missing_module in ['./modules']

    Attributes:
        The exception inherits standard Exception attributes and can include
        custom error messages providing specific details about the missing
        module and search context.

    Related Exceptions:
        - FileNotFoundError: For general file system access issues
        - ImportError: For Python module import failures after discovery
        - PermissionError: For file access permission issues

    Prevention:
        - Validate module names before attempting discovery
        - Verify module directory accessibility during configuration
        - Implement module existence checks in critical paths
        - Provide clear error messages with suggested corrections
        - Use module validation in development and testing workflows

    Framework Integration:
        ModuleNotFound integrates with FTL's error handling throughout:
        - CLI tools for user-friendly error reporting
        - Gate building for dependency validation
        - Remote execution for module availability checking
        - Testing frameworks for module discovery validation

    Note:
        This exception focuses specifically on module discovery failures.
        Subsequent module loading, parsing, or execution errors are handled
        by other exception types or standard Python exceptions as appropriate.
    """

    pass


class ProtocolError(Exception):
    """Exception raised when FTL communication protocol violations occur.

    This exception is raised when errors are detected in FTL's custom message
    protocol used for communication between FTL components, particularly in
    gate-to-gate communication and remote execution coordination. It indicates
    malformed messages, protocol violations, or communication failures.

    Common Scenarios:
        - Invalid message length prefixes in protocol streams
        - Malformed JSON in message payloads
        - Unexpected message format or structure
        - Protocol version mismatches between components
        - Corrupted data during transmission
        - Incomplete message reads due to connection issues

    Usage Context:
        This exception is typically raised by:
        - read_message() in message.py when protocol parsing fails
        - Gate communication handlers when invalid messages are received
        - SSH gate coordination when protocol errors are detected
        - Remote execution when message format validation fails

    Protocol Details:
        FTL uses a length-prefixed JSON message protocol:
        - 8-character hexadecimal length prefix (e.g., "0000001a")
        - JSON message body: [message_type, message_data]
        - Protocol errors occur when this format is violated

    Handling Strategies:
        - Implement protocol validation and error recovery
        - Log protocol errors for debugging and analysis
        - Retry communication with exponential backoff
        - Gracefully degrade to alternative communication methods
        - Report protocol errors to monitoring systems

    Example:
        >>> from faster_than_light.exceptions import ProtocolError
        >>> # In message reading context
        >>> try:
        ...     message = await read_message(reader)
        ... except ProtocolError as e:
        ...     print(f"Protocol error: {e}")
        ...     # Handle by closing connection and retrying
        Protocol error: Invalid hex length: b'invalid!'

        >>> # In gate communication context
        >>> try:
        ...     result = await communicate_with_gate(gate, message)
        ... except ProtocolError as e:
        ...     logger.error(f"Gate communication failed: {e}")
        ...     # Handle by reconnecting to gate

        >>> # Custom protocol error with context
        >>> raise ProtocolError(f"Invalid message format: expected JSON array, got {type(data)}")

    Error Information:
        ProtocolError messages typically include:
        - Description of the specific protocol violation
        - Context about the expected vs. actual message format
        - Raw data that caused the error (when safe to include)
        - Position in the communication stream where error occurred

    Debugging Support:
        - Include partial message data for analysis
        - Provide context about communication state
        - Log protocol errors with sufficient detail for reproduction
        - Support protocol debugging and analysis tools

    Related Exceptions:
        - json.JSONDecodeError: For JSON parsing failures in messages
        - ConnectionError: For underlying network communication issues
        - TimeoutError: For communication timeouts
        - ValueError: For general data validation failures

    Prevention:
        - Implement robust message validation before sending
        - Use protocol version negotiation for compatibility
        - Add checksums or integrity verification to messages
        - Implement graceful handling of partial reads
        - Test protocol implementations with malformed data

    Recovery Strategies:
        - Attempt to resynchronize protocol state
        - Close and reestablish connections on protocol errors
        - Implement message acknowledgment and retry logic
        - Fall back to alternative communication methods
        - Log errors for later analysis and protocol improvement

    Framework Integration:
        ProtocolError integrates with FTL's communication system:
        - SSH gate coordination for reliable remote communication
        - Message protocol implementation in message.py
        - Remote execution error handling and recovery
        - Monitoring and alerting systems for communication health

    Security Considerations:
        - Avoid including sensitive data in error messages
        - Limit exposure of internal protocol details
        - Prevent protocol errors from causing information leakage
        - Implement rate limiting to prevent protocol abuse

    Note:
        ProtocolError focuses specifically on message protocol violations.
        Network-level errors, authentication failures, and other communication
        issues are typically handled by standard Python exceptions or other
        FTL-specific exception types as appropriate.
    """

    pass
