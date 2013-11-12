# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse

import six

from . import commands


def main():
    """
    The top-level entry point for the asv script.

    Most of the real work is handled by the subcommands in the
    commands subpackage.
    """
    parser = argparse.ArgumentParser(
        "Airspeed Velocity: Simple benchmark reporting tool for Python")

    parser.add_argument(
        "config", nargs="?",
        help="Benchmark configuration file",
        default='asv.conf.json')

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands')

    for key, val in six.iteritems(commands.__dict__):
        if hasattr(val, 'setup_arguments'):
            val.setup_arguments(subparsers)

    args = parser.parse_args()

    args.func(args)
