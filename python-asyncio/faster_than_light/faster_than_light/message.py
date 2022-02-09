
import json
from typing import NamedTuple, Any

class GateMessage(NamedTuple):
    message_type: str
    message_body: Any


def send_message(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data]).encode()
    writer.write('{:08x}'.format(len(message)).encode())
    writer.write(message)


def send_message_str(writer, msg_type, msg_data):
    message = json.dumps([msg_type, msg_data])
    writer.write('{:08x}'.format(len(message)))
    writer.write(message)


async def read_message(reader):
    length = await reader.read(8)
    value = await reader.read(int(length, 16))
    return json.loads(value)

def read_message_syn(reader):
    length = reader.read(8)
    value = reader.read(int(length, 16))
    return json.loads(value)
