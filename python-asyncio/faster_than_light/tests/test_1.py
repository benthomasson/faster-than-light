

import os
import pytest
from pprint import pprint
from faster_than_light.inventory import load_inventory
from faster_than_light.module import check_output
from faster_than_light.module import run_module, run_ftl_module
from faster_than_light.util import clean_up_ftl_cache, clean_up_tmp

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.asyncio
async def test_checkoutput():
    os.chdir(HERE)
    output = await check_output('ping')
    print(output)
    assert output
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_timetest():
    os.chdir(HERE)
    output = await run_module(load_inventory('inventory.yml'), ['modules'], 'timetest')
    pprint(output)
    assert output['localhost']
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest():
    os.chdir(HERE)
    output = await run_module(load_inventory('inventory.yml'), ['modules'], 'argtest')
    pprint(output)
    assert output['localhost']
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest_remote():
    os.chdir(HERE)
    output = await run_module(load_inventory('inventory2.yml'), ['modules'], 'argtest')
    pprint(output)
    assert output['localhost']
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_ftl_module():
    os.chdir(HERE)
    output = await run_ftl_module(load_inventory('inventory.yml'),
                                  ['ftl_modules'],
                                  'argtest')
    pprint(output)
    assert output['localhost']
    assert output['localhost'] == {'args': (), 'kwargs': {}}
    clean_up_ftl_cache()
    clean_up_tmp()
