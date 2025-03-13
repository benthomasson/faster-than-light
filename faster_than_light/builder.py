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
import logging
import sys
import click

from typing import Optional, List

from faster_than_light.gate import build_ftl_gate

logger = logging.getLogger('builder')

@click.command
@click.option('--ftl-module', '-f', multiple=True)
@click.option('--module', '-m', multiple=True)
@click.option('--module-dir', '-M', multiple=True)
@click.option('--requirements', '-r', multiple=True)
@click.option('--interpreter', '-I')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--debug', '-d', is_flag=True)
def main(ftl_module, module, module_dir, requirements, interpreter, verbose, debug):

    modules = module
    ftl_modules = ftl_module
    module_dirs = module_dir

    dependencies = None
    for reqs in requirements:
        with open(reqs) as f:
            dependencies = [x for x in f.read().splitlines() if x]

    if not interpreter:
        interpreter = "/usr/bin/python3"

    gate = build_ftl_gate(modules, module_dirs, dependencies, interpreter)
    print(gate)
    return 0

def entry_point() -> None:
    main(sys.argv[1:])  # pragma: no cover
