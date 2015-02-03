# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six

from . import Command
from .run import Run
from .compare import unroll_result

from ..console import truncate_left, color_print
from ..repo import get_repo
from .. import results
from .. import util


class Continuous(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "continuous", help="Compare two commits directly",
            description="""Run a side-by-side comparison of two commits for
            continuous integration.""")

        parser.add_argument(
            'branch', nargs=1, default='master',
            help="""The HEAD branch to test.  This commit and its
            parent commit will be used as the two commits for
            comparison.""")
        parser.add_argument(
            '--factor', "-f", nargs='?', type=float, default=2.0,
            help="""The factor above or below which a result is
            considered problematic.  For example, with a factor of 2,
            if a benchmark gets twice as slow or twice as fast, it
            will be displayed in the results list.""")
        parser.add_argument(
            "--bench", "-b", type=str, nargs="*",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--machine", "-m", nargs='?', type=str, default=None,
            help="""Use the given name to retrieve machine
            information.  If not provided, the hostname is used.  If
            no entry with that name is found, and there is only one
            entry in ~/.asv-machine.json, that one entry will be
            used.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, branch=args.branch[0], factor=args.factor,
            bench=args.bench, machine=args.machine
        )

    @classmethod
    def run(cls, conf, branch="master", factor=2.0, bench=None,
            machine=None):
        repo = get_repo(conf)
        repo.pull()

        repo.checkout_remote_branch('origin', branch)
        head = repo.get_hash_from_head()

        repo.checkout_parent()
        parent = repo.get_hash_from_head()

        commit_hashes = [head, parent]
        run_objs = {}

        result = Run.run(
            conf, range_spec=commit_hashes, bench=bench,
            machine=machine, _returns=run_objs)
        if result:
            return result

        tabulated = []
        all_benchmarks = {}
        for commit_hash in commit_hashes:
            subtab = {}
            totals = {}

            for env in run_objs['environments']:
                filename = results.get_filename(
                    run_objs['machine_params']['machine'], commit_hash, env.name)
                filename = os.path.join(conf.results_dir, filename)
                result = results.Results.load(filename)

                for benchmark_name, benchmark in six.iteritems(run_objs['benchmarks']):
                    for name, value in unroll_result(benchmark_name,
                                                     result.results.get(benchmark_name, None)):
                        if value is not None:
                            all_benchmarks[name] = benchmark
                            subtab.setdefault(name, 0.0)
                            totals.setdefault(name, 0)
                            subtab[name] += value
                            totals[name] += 1

            for name in totals.keys():
                subtab[name] /= totals[name]

            tabulated.append(subtab)

        after, before = tabulated

        table = []
        slowed_down = False
        for name, benchmark in six.iteritems(all_benchmarks):
            change = after[name] / before[name]
            if change > factor or change < 1.0 / factor:
                table.append(
                    (change, before[name], after[name], name, benchmark))
            if change > factor:
                slowed_down = True

        print()

        if not len(table):
            color_print("BENCHMARKS NOT SIGNIFICANTLY CHANGED.\n", 'green')
            return 0

        table.sort(reverse=True)

        color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')
        print()
        color_print(
            "{0:40s}   {1:>8}   {2:>8}   {3:>8}\n".format("BENCHMARK", "BEFORE", "AFTER", "FACTOR"),
            'blue')
        for change, before, after, name, benchmark in table:
            before_display = util.human_value(before, benchmark['unit'])
            after_display = util.human_value(after, benchmark['unit'])

            print("{0:40s}   {1:>8}   {2:>8}   {3:.8f}x".format(
                truncate_left(name, 40),
                before_display, after_display, change))

        color_print(
            "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')

        return slowed_down
