
import pytest
import util
import faster_than_light as ftl
from faster_than_light.inventory import load_inventory
from config import settings
import sys
from pprint import pprint


@pytest.mark.asyncio
async def test_uri():
    uri, path = util.find_module('ansible.builtin.uri')
    assert uri
    result = await ftl.run_module(load_inventory('inventory.yml'), [path], 'uri', module_args=dict(url="https://www.redhat.com"))
    pprint(result)
    assert result['localhost']['msg'] == 'OK (unknown bytes)'
    assert result['localhost']['status'] == 200
