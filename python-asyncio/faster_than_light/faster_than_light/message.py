
import json


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
    writer.write('{:08x}'.format(len(message)))
    writer.write(message)


async def read_message(reader):
    while True:
        length = await reader.read(8)
        try:
            value = await reader.read(int(length, 16))
        except ValueError:
            #print(f'length {length}')
            raise
        return json.loads(value)
