"""
Usage:
    ftl [options]

Options:
    -h, --help                  Show this page
    -f=<f>, --ftl-module=<f>    FTL module
    -m=<m>, --module=<m>        Module
    -M=<M>, --module-dir=<M>    Module directory
    -i=<i>, --inventory=<i>     Inventory
    -r=<r>, --requirements      Python requirements
    -a=<a>, --args=<a>          Module arguments
    --debug                     Show debug logging
    --verbose                   Show verbose logging
"""
import asyncio
from docopt import docopt
import logging
import sys
from .module import run_module
from .module import run_ftl_module
from .inventory import load_inventory
from pprint import pprint

from typing import Optional, List, Dict

logger = logging.getLogger("cli")


def parse_module_args(args: str) -> Dict[str, str]:
    if args:
        key_value_pairs = args.split(" ")
        key_value_tuples = [tuple(i.split("=")) for i in key_value_pairs]
        return {k: v for k, v in key_value_tuples}
    else:
        return {}


async def main(args: Optional[List[str]] = None) -> int:
    if args is None:
        args = sys.argv[1:]   # pragma: no cover
    parsed_args = docopt(__doc__, args)
    if parsed_args["--debug"]:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args["--verbose"]:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    dependencies = None
    if parsed_args["--requirements"]:
        with open(parsed_args["--requirements"]) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    if parsed_args["--module"]:
        output = await run_module(
            load_inventory(parsed_args["--inventory"]),
            [parsed_args["--module-dir"]],
            parsed_args["--module"],
            modules=[parsed_args["--module"]],
            module_args=parse_module_args(parsed_args["--args"]),
            dependencies=dependencies,
        )
        pprint(output)
    elif parsed_args["--ftl-module"]:
        output = await run_ftl_module(
            load_inventory(parsed_args["--inventory"]),
            [parsed_args["--module-dir"]],
            parsed_args["--ftl-module"],
            module_args=parse_module_args(parsed_args["--args"]),
        )
        pprint(output)
    return 0


def entry_point() -> None:
    asyncio.run(main(sys.argv[1:]))   # pragma: no cover
