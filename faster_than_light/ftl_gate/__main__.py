import asyncio
import json
import os
import sys
import tempfile
import base64
import ftl_gate  # type: ignore
import importlib.resources
import shutil
import logging
import traceback
import stat
from typing import Any, Optional, Union, Tuple, Dict, List, cast

logger = logging.getLogger("ftl_gate")


class ModuleNotFoundException(Exception):
    pass

class StdinReader:

    async def read(self, n: int) -> bytes:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, sys.stdin.read, n)
        if isinstance(result, str):
            result = result.encode()
        return cast(bytes, result)


class StdoutWriter:

    def write(self, data: bytes) -> None:
        sys.stdout.write(data.decode())


async def connect_stdin_stdout() -> Tuple[Union[asyncio.StreamReader, StdinReader], Union[asyncio.StreamWriter, StdoutWriter]]:
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
    try:
        module.decode()
        return False
    except UnicodeDecodeError:
        return True


def is_new_style_module(module: bytes) -> bool:
    if b"AnsibleModule(" in module:
        return True
    else:
        return False


def is_want_json_module(module: bytes) -> bool:
    if b"WANT_JSON" in module:
        return True
    else:
        return False


def get_python_path() -> str:
    return os.pathsep.join(sys.path)


async def gate_run_module(writer: Union[asyncio.StreamWriter, StdoutWriter], module_name: str, module: Optional[str] = None, module_args: Optional[Dict[str, Any]] = None) -> None:
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

    module_compiled = compile(base64.b64decode(module), module_name, "exec")

    globals_dict: Dict[str, Any] = {"__file__": module_name}
    locals_dict: Dict[str, Any] = {}

    exec(module_compiled, globals_dict, locals_dict)
    logger.info("Calling FTL module")
    result = await locals_dict["main"]()
    logger.info("Sending FTLModuleResult")
    send_message(writer, "FTLModuleResult", dict(result=result))


async def main(args: List[str]) -> Optional[int]:

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
