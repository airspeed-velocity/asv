# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .run import Run

from . import common_args


class Dev(Run):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "dev", help="Do a test run of a benchmark suite during development",
            description="""
                This runs a benchmark suite in a mode that is useful
                during development.  It is equivalent to ``asv run
                --quick --show-stderr --python=same``""")

        common_args.add_bench(parser)
        common_args.add_machine(parser)
        common_args.add_python(parser)
        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf, bench=args.bench, machine=args.machine, python=args.python)

    @classmethod
    def run(cls, conf, bench=None, python="same", machine=None, _machine_file=None):
        return super(cls, Dev).run(conf=conf, bench=bench, show_stderr=True, quick=True,
                                   python=python, machine=machine, dry_run=True,
                                   _machine_file=_machine_file)
