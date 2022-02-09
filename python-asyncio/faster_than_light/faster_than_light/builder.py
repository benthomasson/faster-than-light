"""
Usage:
    ftl-gate-builder [options]

Options:
    -h, --help                  Show this page
    --debug                     Show debug logging
    --verbose                   Show verbose logging
    -f=<f>, --ftl-module=<f>    FTL module
    -m=<m>, --module=<m>        Module
    -M=<M>, --module-dir=<M>    Module directory
    -r=<r>, --requirements=<r>  Python requirements
    -I=<I>, --interpreter=<I>   Python interpreter to use
"""
from docopt import docopt
import logging
import sys

from typing import Optional, List

from faster_than_light.gate import build_ftl_gate

logger = logging.getLogger('builder')


def main(args: Optional[List[str]]=None) -> int:
    if args is None:
        args = sys.argv[1:]
    parsed_args = docopt(__doc__, args)
    if parsed_args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    dependencies = None
    if parsed_args['--requirements']:
        with open(parsed_args['--requirements']) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    modules = []
    module_dirs = []
    if parsed_args['--module']:
        modules.append(parsed_args['--module'])
    if parsed_args['--module-dir']:
        module_dirs.append(parsed_args['--module-dir'])
    interpreter = sys.executable
    if parsed_args['--interpreter']:
        interpreter = parsed_args['--interpreter']
    gate = build_ftl_gate(modules, module_dirs, dependencies, interpreter)
    print(gate)
    return 0

def entry_point() -> None:
    main(sys.argv[1:])
