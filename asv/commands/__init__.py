# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import argparse
import sys

import six

from .. import config
from .. import util
from .. import __version__


# This list is ordered in order of average workflow
command_order = [
    'Quickstart',
    'Machine',
    'Setup',
    'Run',
    'Dev',
    'Continuous',
    'Find',
    'Rm',
    'Publish',
    'Preview',
    'Profile',
    'Update',
    'Compare'
]


class Command(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        # TODO: Document me
        raise NotImplementedError()

    @classmethod
    def run_from_args(cls, args):
        from ..plugin_manager import plugin_manager
        conf = config.Config.load(args.config)
        for plugin in conf.plugins:
            plugin_manager.import_plugin(plugin)
        return cls.run_from_conf_args(conf, args)

    @classmethod
    def run_from_conf_args(cls, conf, args):
        raise NotImplementedError()


def make_argparser():
    """
    The top-level entry point for the asv script.

    Most of the real work is handled by the subcommands in the
    commands subpackage.
    """
    def help(args):
        parser.print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(
        "asv",
        description="Airspeed Velocity: Simple benchmarking tool for Python")

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Increase verbosity")

    parser.add_argument(
        "--config",
        help="Benchmark configuration file",
        default='asv.conf.json')

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
        help="Print program version")

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands')

    help_parser = subparsers.add_parser(
        "help", help="Display usage information")
    help_parser.set_defaults(func=help)

    commands = dict((x.__name__, x) for x in util.iter_subclasses(Command))

    for command in command_order:
        commands[str(command)].setup_arguments(subparsers)
        del commands[command]

    for name, command in sorted(six.iteritems(commands)):
        command.setup_arguments(subparsers)

    return parser, subparsers


def _make_docstring():
    parser, subparsers = make_argparser()

    lines = []
    for p in six.itervalues(subparsers.choices):
        lines.append(p.prog)
        lines.append('-' * len(p.prog))
        lines.append('::')
        lines.append('')
        lines.extend('   ' + x for x in p.format_help().splitlines())
        lines.append('')

    return '\n'.join(lines)
