# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os
import sys

from . import commands, util
from .console import log


def main():
    parser, subparsers = commands.make_argparser()

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    log.enable(args.verbose)

    args.config = os.path.abspath(args.config)

    # Use the path to the config file as the cwd for the remainder of
    # the run
    dirname = os.path.dirname(args.config)
    os.chdir(dirname)

    try:
        result = args.func(args)
    except util.UserError as e:
        log.error(str(e))
        sys.exit(1)
    finally:
        log.flush()

    if result is None:
        result = 0

    sys.exit(result)
