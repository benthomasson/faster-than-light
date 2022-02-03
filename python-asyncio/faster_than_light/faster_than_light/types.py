

from typing import NamedTuple, Any

from asyncssh.connection import SSHClientConnection
from asyncssh.process import SSHClientProcess


class Gate(NamedTuple):
    conn: SSHClientConnection
    gate_process: SSHClientProcess
    temp_dir: str
