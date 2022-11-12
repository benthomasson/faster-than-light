
import json
import logging
from typing import NamedTuple, Any
from .exceptions import ProtocolError

logger = logging.getLogger(__name__)


class GateMessage(NamedTuple):
    message_type: str
    message_body: Any


def send_message(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data]).encode()
    #print('{:08x}'.format(len(message)).encode())
    #print(message)
    writer.write('{:08x}'.format(len(message)).encode())
    writer.write(message)


def send_message_str(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data])
    #print('{:08x}'.format(len(message)))
    #print(message)
    try:
        writer.write('{:08x}'.format(len(message)))
        writer.write(message)
    except BrokenPipeError:
        logger.error('BrokenPipeError')


async def read_message(reader):
    while True:
        length = await reader.read(8)
        if not length:
            return None
        try:
            value = await reader.read(int(length, 16))
        except ValueError:
            raise ProtocolError(length + await reader.read())
        return json.loads(value)
