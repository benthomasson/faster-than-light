
import base64
import sys
import os
from functools import partial

from io import StringIO

from typing import Dict, Optional, Callable, Tuple
from .types import Gate
from .message import send_message_str, read_message_syn
from .util import process_module_result

from receptorctl.socket_interface import ReceptorControl


async def run_module_through_receptor(
    host_name: str,
    host: Dict,
    module: str,
    module_args: Dict,
    remote_runner: Callable,
    gate_cache: Optional[Dict[str, Gate]],
    gate_builder: Callable,
) -> Tuple[str, Dict]:
    module_name = os.path.basename(module)
    buf = StringIO()
    send_message_str(buf, "Hello", {})
    with open(module, "rb") as f:
        module_text = base64.b64encode(f.read()).decode()
    send_message_str(
        buf,
        "Module",
        dict(module=module_text, module_name=module_name, module_args=module_args),
    )
    send_message_str(buf, "Shutdown", {})
    rc = ReceptorControl('/tmp/foo.sock')
    result = rc.submit_work('ftlgate', buf.getvalue())
    resultsfile = rc.get_work_results(result['unitid'])
    hello = read_message_syn(resultsfile)
    module_result = read_message_syn(resultsfile)
    goodbye = read_message_syn(resultsfile)

    return host_name, process_module_result(module_result)
