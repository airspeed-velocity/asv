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
                --quick --show-stderr --python=same``""")

        parser.add_argument(
            "--bench", "-b", type=str, action="append",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--python", type=str,
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
        parser.add_argument(
            "--machine", "-m", type=str, default=None,
            help="""Use the given name to retrieve machine
            information.  If not provided, the hostname is used.  If
            that is not found, and there is only one entry in
            ~/.asv-machine.json, that one entry will be used.""")

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
