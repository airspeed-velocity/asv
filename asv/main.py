# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys

import six

from . import commands
from .console import console


def main():
    def help(args):
        parser.print_help()
        sys.exit(0)

    console.enable()

    parser, subparsers = commands.make_argparser()

    help_parser = subparsers.add_parser(
        "help", help="Display usage information")
    help_parser.set_defaults(func=help)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except RuntimeError as e:
        console.error(six.text_type(e))
        sys.exit(1)

    console._newline()
