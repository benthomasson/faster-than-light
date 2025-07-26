import asyncio
import os
import subprocess
from pprint import pprint

import pytest

from faster_than_light.exceptions import ModuleNotFound
from faster_than_light.inventory import load_inventory
from faster_than_light.local import check_output
from faster_than_light.module import run_ftl_module, run_module
from faster_than_light.ssh import remove_item_from_cache
from faster_than_light.util import clean_up_ftl_cache, clean_up_tmp

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.asyncio
async def test_checkoutput():
    os.chdir(HERE)
    output = await check_output("ping")
    print(output)
    assert output
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_not_found():
    os.chdir(HERE)
    with pytest.raises(ModuleNotFound):
        await run_module(
            load_inventory("inventory.yml"), ["modules"], "SDFAVADFBG_not_found_DFDFDF"
        )


@pytest.mark.asyncio
async def test_run_module_timetest():
    os.chdir(HERE)
    output = await run_module(load_inventory("inventory.yml"), ["modules"], "timetest")
    pprint(output)
    assert output["localhost"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest():
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest_remote():
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory2.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_ftl_module():
    os.chdir(HERE)
    output = await run_ftl_module(
        load_inventory("inventory.yml"), ["ftl_modules"], "argtest"
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"] == {"args": (), "kwargs": {}}
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_ftl_module_remote():
    os.chdir(HERE)
    output = await run_ftl_module(
        load_inventory("inventory2.yml"), ["ftl_modules"], "argtest"
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"] == {"args": [], "kwargs": {}}
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_want_json():
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory.yml"),
        ["modules"],
        "want_json",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == '{"somekey": "somevalue"}'
    assert output["localhost"]["files"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_new_style():
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory.yml"),
        ["modules"],
        "new_style",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["files"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_c_module():
    os.chdir(os.path.join(HERE, "modules"))
    subprocess.check_output("gcc c_module.c -o c_module", shell=True)
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory.yml"),
        ["modules"],
        "c_module",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_bad_output():
    os.chdir(HERE)
    output = await run_module(
        load_inventory("inventory.yml"),
        ["modules"],
        "bad_output",
        module_args=dict(somekey="somevalue"),
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["error"]
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest_remote_cached():
    os.chdir(HERE)
    cache = dict()
    output = await run_module(
        load_inventory("inventory2.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
        gate_cache=cache,
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    assert cache
    await remove_item_from_cache(cache)
    assert not cache
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest_remote_cached2():
    os.chdir(HERE)
    cache = dict()
    output = await run_module(
        load_inventory("inventory2.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
        gate_cache=cache,
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    assert cache
    output = await run_module(
        load_inventory("inventory2.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
        gate_cache=cache,
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    assert cache
    await remove_item_from_cache(cache)
    assert not cache
    clean_up_ftl_cache()
    clean_up_tmp()


@pytest.mark.asyncio
async def test_run_module_argtest_host():
    os.chdir(HERE)
    cache = dict()
    output = await run_module(
        load_inventory("inventory3.yml"),
        ["modules"],
        "argtest",
        module_args=dict(somekey="somevalue"),
        gate_cache=cache,
    )
    pprint(output)
    assert output["localhost"]
    assert output["localhost"]["args"]
    assert output["localhost"]["executable"]
    assert output["localhost"]["more_args"] == "somekey=somevalue"
    assert output["localhost"]["files"]
    assert cache
    await remove_item_from_cache(cache)
    assert not cache
    clean_up_ftl_cache()
    clean_up_tmp()


def test_synchronous():
    """Test running async FTL code from a synchronous context using asyncio.run()."""

    async def run_test():
        os.chdir(HERE)
        cache = dict()
        output = await run_module(
            load_inventory("inventory3.yml"),
            ["modules"],
            "argtest",
            module_args=dict(somekey="somevalue"),
            gate_cache=cache,
        )
        pprint(output)
        assert output["localhost"]
        assert output["localhost"]["args"]
        assert output["localhost"]["executable"]
        assert output["localhost"]["more_args"] == "somekey=somevalue"
        assert output["localhost"]["files"]
        assert cache
        await remove_item_from_cache(cache)
        assert not cache
        clean_up_ftl_cache()
        clean_up_tmp()

    # Use modern asyncio.run() instead of deprecated get_event_loop()
    asyncio.run(run_test())
