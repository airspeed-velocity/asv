# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys

import six

from . import commands
from .console import log


def main():
    def help(args):
        parser.print_help()
        sys.exit(0)

    parser, subparsers = commands.make_argparser()

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Increase verbosity")

    help_parser = subparsers.add_parser(
        "help", help="Display usage information")
    help_parser.set_defaults(func=help)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    log.enable(args.verbose)

    try:
        args.func(args)
    except RuntimeError as e:
        log.error(six.text_type(e))
        sys.exit(1)

    sys.stdout.write('\n')
