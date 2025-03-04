import asyncio
import json
import os
import sys
import tempfile
import base64
import ftl_gate
import importlib.resources
import shutil
import logging
import traceback
import stat

logger = logging.getLogger("ftl_gate")


class StdinReader(object):

    async def read(self, n):
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, sys.stdin.read, n)
        if isinstance(result, str):
            result = result.encode()
        return result


class StdoutWriter(object):

    def write(self, data):
        sys.stdout.write(data.decode())


async def connect_stdin_stdout():
    loop = asyncio.get_event_loop()
    try:
        # Try to connect to pipes
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    except ValueError:
        # Fall back to simple reader and writer
        reader = StdinReader()
        writer = StdoutWriter()
    return reader, writer


async def read_message(reader):

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
                        return json.loads(value)
                    except BaseException:
                        # print(value)
                        raise
                else:
                    continue


def send_message(writer, msg_type, data):

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


async def check_output(cmd, env=None, stdin=None):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await proc.communicate(stdin)
    return stdout, stderr


def is_binary_module(module):
    try:
        module.decode()
        return False
    except UnicodeDecodeError:
        return True


def is_new_style_module(module):
    if b"AnsibleModule(" in module:
        return True
    else:
        return False


def is_want_json_module(module):
    if b"WANT_JSON" in module:
        return True
    else:
        return False


def get_python_path():
    return os.pathsep.join(sys.path)


async def gate_run_module(writer, module_name, module=None, module_args=None):
    logger.info(module_name)
    tempdir = tempfile.mkdtemp(prefix="ftl-module")
    try:
        module_file = os.path.join(tempdir, f"ftl_{module_name}")
        logger.info(module_file)
        env = os.environ.copy()
        env["PYTHONPATH"] = get_python_path()
        if module is not None:
            logger.info("loading module from message")
            module = base64.b64decode(module)
            with open(module_file, "wb") as f:
                f.write(module)
        else:
            logger.info("loading module from ftl_gate")
            modules = importlib.resources.files(ftl_gate)
            with open(module_file, "wb") as f2:
                module = importlib.resources.files(ftl_gate).joinpath(module_name).read_bytes()
                f2.write(module)
        if is_binary_module(module):
            logger.info("is_binary_module")
            args = os.path.join(tempdir, "args")
            with open(args, "w") as f:
                f.write(json.dumps(module_args))
            os.chmod(module_file, stat.S_IEXEC | stat.S_IREAD)
            stdout, stderr = await check_output(f"{module_file} {args}")
        elif is_new_style_module(module):
            logger.info("is_new_style_module")
            stdout, stderr = await check_output(
                f"{sys.executable} {module_file}",
                stdin=json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)).encode(),
                env=env,
            )
        elif is_want_json_module(module):
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



async def run_ftl_module(writer, module_name, module, module_args=None):

    module_compiled = compile(base64.b64decode(module), module_name, "exec")

    globals = {"__file__": module_name}
    locals = {}

    exec(module_compiled, globals, locals)
    logger.info("Calling FTL module")
    result = await locals["main"]()
    logger.info("Sending FTLModuleResult")
    send_message(writer, "FTLModuleResult", dict(result=result))


async def main(args):

    logging.basicConfig(filename="/tmp/ftl_gate.log", level=logging.DEBUG)

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
                return
            elif msg_type == "Hello":
                logger.info("hello")
                send_message(writer, msg_type, data)
            elif msg_type == "Module":
                logger.info("Module")
                await gate_run_module(writer, **data)
            elif msg_type == "FTLModule":
                logger.info("FTLModule")
                await run_ftl_module(writer, **data)
            elif msg_type == "Shutdown":
                logger.info("Shutdown")
                send_message(writer, "Goodbye", {})
                return
            else:
                send_message(
                    writer, "Error", dict(message=f"Unknown message type {msg_type}")
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
