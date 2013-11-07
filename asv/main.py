# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse

from . import commands


def main():
    parser = argparse.ArgumentParser(
        "Airspeed Velocity: Simple Github-based benchmark reporting tool for Python")

    parser.add_argument("config", nargs="?",
                        help="Benchmark configuration file",
                        default='')

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands')

    for key, val in commands.__dict__.items():
        if hasattr(val, 'setup_arguments'):
            val.setup_arguments(subparsers)

    args = parser.parse_args()

    args.func(args)
