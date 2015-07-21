# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import argparse

from .. import __version__


def add_global_arguments(parser, suppress_defaults=True):
    # Suppressing defaults is needed in order to allow global
    # arguments both before and after subcommand. Only the top-level
    # parser should have suppress_defaults=False

    if suppress_defaults:
        suppressor = dict(default=argparse.SUPPRESS)
    else:
        suppressor = dict()

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Increase verbosity",
        **suppressor)

    parser.add_argument(
        "--config",
        help="Benchmark configuration file",
        default=(argparse.SUPPRESS if suppress_defaults else 'asv.conf.json'))

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
        help="Print program version",
        **suppressor)


def add_factor(parser):
    parser.add_argument(
        '--factor', "-f", type=float, default=2.0,
        help="""The factor above or below which a result is considered
        problematic.  For example, with a factor of 2, if a benchmark
        gets twice as slow or twice as fast, it will be displayed in
        the results list.""")


def add_show_stderr(parser):
    parser.add_argument(
        "--show-stderr", "-e", action="store_true",
        help="""Display the stderr output from the benchmarks.""")


def add_bench(parser):
    parser.add_argument(
        "--bench", "-b", type=str, action="append",
        help="""Regular expression(s) for benchmark to run.  When not
        provided, all benchmarks are run.""")


def add_machine(parser):
    parser.add_argument(
        "--machine", "-m", type=str, default=None,
        help="""Use the given name to retrieve machine information.
        If not provided, the hostname is used.  If no entry with that
        name is found, and there is only one entry in
        ~/.asv-machine.json, that one entry will be used.""")


def add_python(parser, default=None):
    parser.add_argument(
        "--python", type=str,
        default=default,
        help="""Specify a Python interpreter in which to run the
        benchmarks.  By default, uses the same Python interpreter that
        asv is using.  It may be an executable to be searched for on
        the $PATH, an absolute path, or the special value "same" which
        will use the same Python interpreter that asv is using.  This
        "same" interpreter must have the benchmarked project already
        installed, including its dependencies.  A specific revision
        may not be provided when --python is provided.

        It may also be any string accepted by any of the environment
        plugins.  For example, the conda plugin accepts "2.7" to mean
        create a new Conda environment with Python version 2.7.""")


def add_parallel(parser):
    parser.add_argument(
        "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
        help="""Build (but don't benchmark) in parallel.  The value is
        the number of CPUs to use, or if no number provided, use the
        number of cores on this machine.""")


def positive_int(string):
    try:
        value = int(string)
        if not value > 0:
            raise argparse.ArgumentTypeError("%r is not a positive integer" % (string,))
        return value
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not an integer" % (string,))
