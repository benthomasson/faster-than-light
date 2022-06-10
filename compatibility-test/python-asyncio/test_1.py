
import pytest
import util
import faster_than_light as ftl
from faster_than_light.inventory import load_inventory
from config import settings
import sys


@pytest.mark.asyncio
async def test_1():
    slack, path = util.find_module('community.general.slack')
    assert slack
    result = await ftl.run_module(load_inventory('inventory.yml'), [path], 'slack', module_args=dict(token=settings.SLACK_TOKEN, msg='hi from ftl'))
    print(result)
    result['localhost']['msg'] == 'OK'
