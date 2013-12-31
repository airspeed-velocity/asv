# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse

from .gh_pages import GithubPages
from .machine import Machine
from .preview import Preview
from .publish import Publish
from .quickstart import Quickstart
from .rm import Rm
from .run import Run
from .setup import Setup
from .update import Update

# This list is ordered in order of average workflow
all_commands = [
    Quickstart,
    Machine,
    Setup,
    Run,
    Rm,
    Publish,
    Preview,
    Update,
    GithubPages
]


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
    for command in all_commands:
        command_parsers.append(
            command.setup_arguments(subparsers))

    return parser, command_parsers


def _make_docstring():
    parser, command_parsers = make_argparser()

    lines = []
    for p in command_parsers:
        lines.append(p.prog)
        lines.append('-' * len(p.prog))
        lines.append('::')
        lines.append('')
        lines.extend('   ' + x for x in p.format_help().splitlines())
        lines.append('')

    return '\n'.join(lines)

__doc__ = _make_docstring()
