
"""Type definitions for the Faster Than Light automation framework.

This module defines custom data types used throughout FTL for representing
SSH connections, gate processes, and other framework-specific structures.
"""

from typing import NamedTuple, Any

from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess


class Gate(NamedTuple):
    """Represents an active SSH gate connection for remote module execution.
    
    A Gate encapsulates the components needed for executing modules on a remote
    host through FTL's gate mechanism. It bundles an SSH connection, the gate
    process running on the remote host, and the temporary directory used for
    file operations.
    
    The Gate is designed to be immutable and hashable, making it safe to use
    as dictionary keys and in sets. It follows the NamedTuple pattern for
    easy access to fields while maintaining tuple semantics.
    
    Attributes:
        conn: Active SSH connection to the remote host. Used for file transfers,
            command execution, and maintaining the communication channel.
        gate_process: The remote Python process running the FTL gate. This process
            handles module execution requests and returns results through the
            message protocol.
        temp_dir: Path to the temporary directory on the remote host where gate
            files and module artifacts are stored. Typically "/tmp" but may
            vary by system configuration.
    
    Example:
        >>> gate = Gate(ssh_conn, gate_proc, "/tmp")
        >>> print(f"Connected to {gate.conn.get_transport().get_remote_server_key()}")
        >>> result = await run_module_through_gate(gate.gate_process, "ping", ...)
    
    Note:
        Gates should be properly closed after use to clean up resources and
        terminate the remote gate process. Use close_gate() for proper cleanup.
    """
    conn: SSHClientConnection
    gate_process: SSHClientProcess
    temp_dir: str
