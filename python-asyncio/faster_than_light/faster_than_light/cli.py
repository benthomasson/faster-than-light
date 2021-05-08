

"""
Usage:
    ftl [options]

Options:
    -h, --help                  Show this page
    -m=<m>, --module=<m>        Module
    -M=<M>, --module-dir=<M>    Module directory
    -i=<i>, --inventory=<i>     Inventory
    --debug                     Show debug logging
    --verbose                   Show verbose logging
"""
from docopt import docopt
import logging
import sys

logger = logging.getLogger('cli')


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parsed_args = docopt(__doc__, args)
    if parsed_args['--debug']:
        logging.basicConfig(level=logging.DEBUG)
    elif parsed_args['--verbose']:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    print(parsed_args['--module'])
    print(parsed_args['--module-dir'])
    print(parsed_args['--inventory'])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
