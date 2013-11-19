# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse

import six

from . import commands
from .console import console


def make_argparser():
    """
    The top-level entry point for the asv script.

    Most of the real work is handled by the subcommands in the
    commands subpackage.
    """
    parser = argparse.ArgumentParser(
        "asv",
        description="Airspeed Velocity: Simple benchmarking tool for Python")

    parser.add_argument(
        "--config",
        help="Benchmark configuration file",
        default='asv.conf.json')

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands')

    command_parsers = []
    for name in commands.all_commands:
        command = getattr(commands, name)
        if hasattr(command, 'setup_arguments'):
            command_parsers.append(
                command.setup_arguments(subparsers))

    return parser, command_parsers


def main():
    parser, command_parsers = make_argparser()

    args = parser.parse_args()
    args.func(args)

    console._newline()
