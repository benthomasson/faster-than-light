
import asyncio
import json
import os
import sys
import tempfile
import base64
import ftl_gate
import importlib.resources
import shutil


async def connect_stdin_stdout():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    return reader, writer


async def read_message(reader):

    while True:

        # Messages are Length Value
        # Length is a 8 byte field in hexadecimal
        # Value is a length byte field

        value = b''
        length_hexadecimal = b'0'
        length = 0

        # Read length
        length_hexadecimal = await reader.read(8)
        # If the length_hexadecimal is None then the channel was closed
        if not length_hexadecimal:
            return None

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
                    return None
                value = value.strip()
                # Keep reading until we get a value
                # This is useful for manual debugging
                # Run with python __main__.py
                # Enter: 0000000d
                # Enter: ["Hello", {}]
                # Response should be  0000000d["Hello", {}]
                if value:
                    try:
                        return json.loads(value)
                    except BaseException:
                        print(value)
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
    assert len(message) < 16**8, f'Message {msg_type} is too big.  Break up messages into less than 16**8 bytes'
    writer.write('{:08x}'.format(len(message)).encode())
    writer.write(message)


async def check_output(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()
    return stdout, stderr


async def gate_run_module(writer, module_name, module=None):
    tempdir = tempfile.mkdtemp(prefix="ftl-module")
    try:
        module_file = os.path.join(tempdir, module_name)
        if module is not None:
            with open(module_file, 'wb') as f:
                f.write(base64.b64decode(module))
        else:
            modules = importlib.resources.files(ftl_gate)
            with open(module_file, 'wb') as f2:
                f2.write(importlib.resources.read_binary(ftl_gate, module_name))
        args = os.path.join(tempdir, 'args')
        with open(args, 'w') as f:
            f.write('some args')
        stdout, stderr = await check_output(f'{sys.executable} {module_file} {args}')
        send_message(writer, 'ModuleResult', dict(stdout=stdout.decode(),
                                                  stderr=stderr.decode()))
    finally:
        shutil.rmtree(tempdir)


async def run_ftl_module(writer, module_name, module):

    module_compiled = compile(base64.b64decode(module), module_name, 'exec')

    globals = {'__file__': module_name}
    locals = {}

    exec(module_compiled, globals, locals)
    result = await locals['main']()
    send_message(writer, 'FTLModuleResult', dict(result=result))


async def main(args):

    reader, writer = await connect_stdin_stdout()

    while True:

        try:
            msg_type, data = await read_message(reader)
            if msg_type == 'Hello':
                send_message(writer, msg_type, data)
            elif msg_type == 'Module':
                await gate_run_module(writer, **data)
            elif msg_type == 'FTLModule':
                await run_ftl_module(writer, **data)
            elif msg_type == 'Shutdown':
                return
            else:
                send_message(writer, 'Error', dict(message=f'Unknown message type {msg_type}'))
        except BaseException as e:
            send_message(writer, 'GateSystemError', dict(message=f'Exception {e}'))
            return 1


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
