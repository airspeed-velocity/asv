# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys

import six

from . import commands
from . import console


def main():
    console.console = console._Console()

    parser, command_parsers = commands.make_argparser()

    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as e:
        console.error(six.text_type(e))
        sys.exit(1)

    console._newline()
