# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .run import Run


class Dev(Run):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "dev", help="Do a test run of a benchmark suite during development",
            description="""
                This runs a benchmark suite in a mode that is useful
                during development.  It is equivalent to ``asv run
                --quick --show-exc --python=same``""")

        parser.add_argument(
            "--bench", "-b", type=str, nargs="*",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--python", nargs='?', type=str,
            default="same",
            help="""Specify a Python interpreter in which to run the
            benchmarks.  By default, uses the same Python interpreter
            that `asv` is using.  It may be an executable to be
            searched for on the $PATH, an absolute path, or the
            special value "same" which will use the same Python
            interpreter that asv is using.  This interpreter must have
            the benchmarked project already installed, including its
            dependencies.  A specific revision may not be provided
            when --python is provided.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, bench=args.bench, show_exc=True, quick=True,
            python=args.python, dry_run=True)
