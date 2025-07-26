
import pytest
import util
from config import settings

import faster_than_light as ftl
from faster_than_light.inventory import load_inventory


@pytest.mark.asyncio
async def test_slack():
    slack, path = util.find_module("community.general.slack")
    assert slack
    result = await ftl.run_module(
        load_inventory("inventory.yml"),
        [path],
        "slack",
        module_args=dict(token=settings.SLACK_TOKEN, msg="hi from ftl"),
    )
    print(result)
    assert result["localhost"]["msg"] == "OK"
