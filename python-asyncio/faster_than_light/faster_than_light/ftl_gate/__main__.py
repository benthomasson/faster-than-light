
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

logger = logging.getLogger('ftl_gate')


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


async def check_output(cmd, stdin=None):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate(stdin)
    return stdout, stderr


def is_new_style_module(module):
    if b'AnsibleModule(' in module:
        return True
    else:
        return False

def is_want_json_module(module):
    if b'WANT_JSON' in module:
        return True
    else:
        return False

async def gate_run_module(writer, module_name, module=None, module_args=None):
    logger.info(module_name)
    tempdir = tempfile.mkdtemp(prefix="ftl-module")
    try:
        module_file = os.path.join(tempdir, module_name)
        if module is not None:
            module = base64.b64decode(module)
            with open(module_file, 'wb') as f:
                f.write(module)
        else:
            logger.info("loading from ftl_gate")
            modules = importlib.resources.files(ftl_gate)
            with open(module_file, 'wb') as f2:
                module = importlib.resources.read_binary(ftl_gate, module_name)
                f2.write(module)
        if is_new_style_module(module):
            stdout, stderr = await check_output(f'{sys.executable} {module_file}', stdin=json.dumps(dict(ANSIBLE_MODULE_ARGS=module_args)).encode())
        elif is_want_json_module(module):
            args = os.path.join(tempdir, 'args')
            with open(args, 'w') as f:
                f.write(json.dumps(module_args))
            stdout, stderr = await check_output(f'{sys.executable} {module_file} {args}')
        else:
            args = os.path.join(tempdir, 'args')
            with open(args, 'w') as f:
                if module_args is not None:
                    f.write(" ".join(["=".join([k, v]) for k, v in module_args.items()]))
                else:
                    f.write('')
            stdout, stderr = await check_output(f'{sys.executable} {module_file} {args}')
        send_message(writer, 'ModuleResult', dict(stdout=stdout.decode(),
                                                  stderr=stderr.decode()))
    finally:
        shutil.rmtree(tempdir)


async def run_ftl_module(writer, module_name, module, module_args=None):

    module_compiled = compile(base64.b64decode(module), module_name, 'exec')

    globals = {'__file__': module_name}
    locals = {}

    exec(module_compiled, globals, locals)
    result = await locals['main']()
    send_message(writer, 'FTLModuleResult', dict(result=result))


async def main(args):

    logging.basicConfig(filename="/tmp/ftl_gate.log", level=logging.DEBUG)



    reader, writer = await connect_stdin_stdout()

    while True:

        try:
            msg_type, data = await read_message(reader)
            if msg_type == 'Hello':
                logger.info('hello')
                send_message(writer, msg_type, data)
            elif msg_type == 'Module':
                logger.info('Module')
                await gate_run_module(writer, **data)
            elif msg_type == 'FTLModule':
                logger.info('FTLModule')
                await run_ftl_module(writer, **data)
            elif msg_type == 'Shutdown':
                logger.info('Shutdown')
                return
            else:
                send_message(writer, 'Error', dict(message=f'Unknown message type {msg_type}'))
        except BaseException as e:
            send_message(writer, 'GateSystemError', dict(message=f'Exception {e}'))
            logger.error(f'GateSystemError: {e}')
            logger.error(traceback.format_exc())
            return 1


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
