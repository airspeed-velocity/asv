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

from . import common_args


class Continuous(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "continuous", help="Compare two commits directly",
            description="""Run a side-by-side comparison of two commits for
            continuous integration.""")

        parser.add_argument(
            'base', nargs='?', default=None,
            help="""The commit/branch to compare against. By default, the
            parent of the tested commit.""")
        parser.add_argument(
            'branch', default=None,
            help="""The commit/branch to test. By default, the master branch.""")
        common_args.add_factor(parser)
        common_args.add_show_stderr(parser)
        common_args.add_bench(parser)
        common_args.add_machine(parser)
        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, branch=args.branch, base=args.base, factor=args.factor,
            show_stderr=args.show_stderr, bench=args.bench, machine=args.machine
        )

    @classmethod
    def run(cls, conf, branch=None, base=None, factor=2.0, show_stderr=False, bench=None,
            machine=None, _machine_file=None):
        repo = get_repo(conf)
        repo.pull()

        if branch is None:
            head = repo.get_hash_from_master()
        else:
            head = repo.get_hash_from_name(branch)
        if base is None:
            parent = repo.get_hash_from_parent(head)
        else:
            parent = repo.get_hash_from_name(base)

        commit_hashes = [head, parent]
        run_objs = {}

        result = Run.run(
            conf, range_spec=commit_hashes, bench=bench,
            show_stderr=show_stderr, machine=machine, _returns=run_objs,
            _machine_file=_machine_file)
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

        print("")

        if not len(table):
            color_print("BENCHMARKS NOT SIGNIFICANTLY CHANGED.\n", 'green')
            return 0

        table.sort(reverse=True)

        color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')
        print("")
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
