
import datetime


async def main(*args, **kwargs):

    date = str(datetime.datetime.now())
    return {
        "time": date
    }
