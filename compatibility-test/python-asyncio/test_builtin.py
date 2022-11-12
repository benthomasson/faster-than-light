import pytest
import util
import faster_than_light as ftl
from faster_than_light.inventory import load_inventory
from config import settings
import sys
import os
import shutil
from pprint import pprint
from pathlib import Path


async def run_module_with_inventory(module, **kwargs):
    _, _, module_name = module.rpartition(".")
    command, path = util.find_module(module)
    assert command
    return await ftl.run_module(
        load_inventory("inventory.yml"), [path], module_name, module_args=kwargs
    )


@pytest.mark.asyncio
async def test_assemble():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, "fragments", "a.txt"), 'w') as f:
        f.write("A\n")
    with open(os.path.join(here, "fragments", "b.txt"), 'w') as f:
        f.write("B\n")
    assemble, path = util.find_module("ansible.builtin.assemble")
    assert assemble
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "assemble",
        module_args=dict(src=os.path.join(here, "fragments"), dest="/tmp/assemble_output")
    )
    pprint(result)
    assert result["localhost"]["msg"] == "OK"
    with open("/tmp/assemble_output") as f:
        assert f.read() == 'A\nB\n'
    os.unlink("/tmp/assemble_output")

@pytest.mark.asyncio
async def test_copy():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, "fragments", "a.txt"), 'w') as f:
        f.write("A\n")
    assert os.path.exists(os.path.join(here, "fragments", "a.txt"))
    copy, path = util.find_module("ansible.builtin.copy")
    assert copy
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "copy",
        module_args=dict(src=os.path.join(here, "fragments", "a.txt"), dest="/tmp/copy_output")
    )
    assert os.path.exists(os.path.join(here, "fragments", "a.txt"))
    pprint(result)
    with open("/tmp/copy_output") as f:
        assert f.read() == 'A\n'
    os.unlink("/tmp/copy_output")
    assert os.path.exists(os.path.join(here, "fragments", "a.txt"))

@pytest.mark.asyncio
async def test_cron():
    here = os.path.abspath(os.path.dirname(__file__))
    cron, path = util.find_module("ansible.builtin.cron")
    assert cron
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "cron",
        module_args=dict(name="not here", state="absent")
    )
    pprint(result)
    assert result['localhost']['changed'] == False

@pytest.mark.asyncio
async def test_blockinfile():
    here = os.path.abspath(os.path.dirname(__file__))
    Path("/tmp/blockinfile").touch()
    blockinfile, path = util.find_module("ansible.builtin.blockinfile")
    assert blockinfile
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "blockinfile",
        module_args=dict(path="/tmp/blockinfile", block="foobar")
    )
    pprint(result)
    assert result["localhost"]["msg"] == "Block inserted"
    os.unlink("/tmp/blockinfile")

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
async def test_get_url():
    get_url, path = util.find_module("ansible.builtin.get_url")
    assert get_url
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "get_url",
        module_args=dict(url="https://www.redhat.com", dest="/tmp/output"),
    )
    pprint(result)
    assert os.path.exists("/tmp/output")
    os.unlink("/tmp/output")


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


@pytest.mark.asyncio
async def test_ping():
    ping, path = util.find_module("ansible.builtin.ping")
    assert ping
    result = await ftl.run_module(
        load_inventory("inventory.yml"), [path], "ping", module_args=dict()
    )
    assert result["localhost"]["ping"] == "pong"


@pytest.mark.asyncio
async def test_file():
    file, path = util.find_module("ansible.builtin.file")
    assert file
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "file",
        module_args=dict(path="/tmp/deleteme.txt", state="absent"),
    )
    assert result["localhost"]["changed"] == False


@pytest.mark.asyncio
async def test_file2():
    file, path = util.find_module("ansible.builtin.file")
    assert file
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "file",
        module_args=dict(path="/tmp/touch.txt", state="touch"),
    )
    print(result)
    assert result["localhost"]["changed"] == True

@pytest.mark.asyncio
async def test_find():
    find, path = util.find_module("ansible.builtin.find")
    assert find
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "find",
        module_args=dict(paths="/tmp/")
    )
    print(result)
    assert result["localhost"]["changed"] == False
    assert result["localhost"]["files"] != []

@pytest.mark.asyncio
async def test_git():
    git, path = util.find_module("ansible.builtin.git")
    assert git
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "git",
        module_args=dict(repo="https://github.com/benthomasson/faster-than-light.git", dest="/tmp/ftl-repo")
    )
    print(result)
    assert result["localhost"]["after"]
    assert os.path.exists("/tmp/ftl-repo")
    shutil.rmtree("/tmp/ftl-repo")

@pytest.mark.asyncio
async def test_group():
    group, path = util.find_module("ansible.builtin.group")
    assert group
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "group",
        module_args=dict(name="foobar")
    )
    print(result)
    assert result["localhost"]['msg'] == "Username and password must be provided.\n"

@pytest.mark.asyncio
async def test_user():
    user, path = util.find_module("ansible.builtin.user")
    assert user
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "user",
        module_args=dict(name="foobar")
    )
    print(result)
    assert result["localhost"]['msg'] == 'Cannot create user "foobar".'

@pytest.mark.asyncio
async def test_hostname():
    hostname, path = util.find_module("ansible.builtin.hostname")
    assert hostname
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "hostname",
        module_args=dict(name="foobar")
    )
    print(result)
    assert False

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
