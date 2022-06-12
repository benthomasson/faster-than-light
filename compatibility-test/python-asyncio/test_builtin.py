import pytest
import util
import faster_than_light as ftl
from faster_than_light.inventory import load_inventory
from config import settings
import sys
from pprint import pprint


async def run_module_with_inventory(module, **kwargs):
    _, _, module_name = module.rpartition(".")
    command, path = util.find_module(module)
    assert command
    return await ftl.run_module(
        load_inventory("inventory.yml"), [path], module_name, module_args=kwargs
    )


@pytest.mark.asyncio
async def test_uri():
    uri, path = util.find_module("ansible.builtin.uri")
    assert uri
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "uri",
        module_args=dict(url="https://www.redhat.com"),
    )
    pprint(result)
    assert result["localhost"]["msg"] == "OK (unknown bytes)"
    assert result["localhost"]["status"] == 200


@pytest.mark.asyncio
async def test_command():
    result = await run_module_with_inventory("ansible.builtin.command")
    pprint(result)
    assert result["localhost"]["msg"] == "no command given"


@pytest.mark.asyncio
async def test_command_echo():
    command, path = util.find_module("ansible.builtin.command")
    assert command
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "command",
        module_args=dict(argv=["pwd"]),
    )
    pprint(result)
    assert result["localhost"]["msg"] == ""
    assert result["localhost"]["stdout"]


@pytest.mark.parametrize(
    "module",
    [
        "add_host",
        "assert",
        "shell",
        "debug",
        "raw",
        "group_by",
        "gather_facts",
        "fetch",
        "fail",
        "include_vars",
        "include_tasks",
        "import_playbook",
        "import_role",
        "import_tasks",
        "package",
        "meta",
        "pause",
        "reboot",
        "script",
        "set_fact",
        "set_stats",
        "template",
        "wait_for_connection",
    ],
)
@pytest.mark.asyncio
async def test_empty_modules(module):
    result = await run_module_with_inventory(f"ansible.builtin.{module}")
    pprint(result)
    assert result["localhost"]["error"] == b""
