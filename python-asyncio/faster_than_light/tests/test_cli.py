

import faster_than_light.cli
import pytest
import os
import docopt

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.asyncio
async def test_cli():
    await faster_than_light.cli.main([])



@pytest.mark.asyncio
async def test_cli_debug():
    await faster_than_light.cli.main(['--debug'])


@pytest.mark.asyncio
async def test_cli_verbose():
    await faster_than_light.cli.main(['--verbose'])


@pytest.mark.asyncio
async def test_cli_argtest():
    await faster_than_light.cli.main(['-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml', '-a', 'somekey=somevalue'])


@pytest.mark.asyncio
async def test_cli_argtest2():
    await faster_than_light.cli.main(['-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml'])

@pytest.mark.asyncio
async def test_cli_ftl_argtest():
    await faster_than_light.cli.main(['-M', 'ftl_modules', '-f', 'argtest', '-i', 'inventory.yml', '-a', 'somekey=somevalue'])


@pytest.mark.asyncio
async def test_cli_argtest():
    await faster_than_light.cli.main(['-M', 'modules', '-m', 'argtest', '-i', 'inventory.yml', '-a', 'somekey=somevalue', '--requirements', 'requirements.txt'])
