# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import itertools

from . import Command
from ..machine import iter_machine_files
from ..results import iter_results_for_machine_and_hash
from ..util import human_value, load_json
from ..console import color_print
from .. import util

from . import common_args


def mean(values):
    if all([value is None for value in values]):
        return None
    else:
        values = [value for value in values if value is not None]
        return sum(values) / float(len(values))


def unroll_result(benchmark_name, result):
    """
    Iterate through parameterized result values

    Yields
    ------
    name
        Strings of the form "benchmark_name(value1, value2)" with
        parameter values substituted in. For non-parameterized
        results, simply the benchmark name.
    value
        Benchmark timing or other scalar value.

    """
    if not isinstance(result, dict):
        yield benchmark_name, result
        return

    for params, result in zip(itertools.product(*result['params']),
                              result['result']):
        name = "%s(%s)" % (benchmark_name, ", ".join(params))
        yield name, result


class Compare(Command):

    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "compare",
            help="""Compare the benchmark results between two revisions
                    (averaged over configurations)""",
            description="Compare two sets of results")

        parser.add_argument(
            'revision1',
            help="""The reference revision.""")

        parser.add_argument(
            'revision2',
            help="""The revision being compared.""")

        common_args.add_factor(parser)

        parser.add_argument(
           '--split', '-s', action='store_true',
           help="""Split the output into a table of benchmarks that have
           improved, stayed the same, and gotten worse.""")

        parser.add_argument(
            '--machine', '-m', type=str, default=None,
            help="""The machine to compare the revisions for.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf,
                       hash_1=args.revision1,
                       hash_2=args.revision2,
                       factor=args.factor, split=args.split,
                       machine=args.machine)

    @classmethod
    def run(cls, conf, hash_1, hash_2, factor=2, split=False, machine=None):

        machines = []
        for path in iter_machine_files(conf.results_dir):
            d = load_json(path)
            machines.append(d['machine'])

        if len(machines) == 0:
            raise util.UserError("No results found")
        elif machine is None:
            if len(machines) > 1:
                raise util.UserError(
                    "Results available for several machines: {0} - "
                    "specify which one to use with the --machine option".format(
                        '/'.join(machines)))
            else:
                machine = machines[0]
        elif not machine in machines:
            raise util.UserError(
                "Results for machine '{0} not found".format(machine))

        results_1 = {}
        results_2 = {}

        for result in iter_results_for_machine_and_hash(
                conf.results_dir, machine, hash_1):
            for key in result.results:
                for name, value in unroll_result(key, result.results[key]):
                    if name not in results_1:
                        results_1[name] = []
                    results_1[name].append(value)

        for result in iter_results_for_machine_and_hash(
                conf.results_dir, machine, hash_2):
            for key in result.results:
                for name, value in unroll_result(key, result.results[key]):
                    if name not in results_2:
                        results_2[name] = []
                    results_2[name].append(value)

        if len(results_1) == 0:
            raise util.UserError(
                "Did not find results for commit {0}".format(hash_1))

        if len(results_2) == 0:
            raise util.UserError(
                "Did not find results for commit {0}".format(hash_2))

        benchmarks_1 = set(results_1.keys())
        benchmarks_2 = set(results_2.keys())

        common_benchmarks = sorted(list(benchmarks_1 & benchmarks_2))

        bench = {}

        if split:
            bench['green'] = []
            bench['red'] = []
            bench['default'] = []
        else:
            bench['all'] = []

        for benchmark in common_benchmarks:

            time_1 = mean(results_1[benchmark])
            time_2 = mean(results_2[benchmark])

            if util.is_na(time_1) or util.is_na(time_2):
                ratio = 'n/a'
            else:
                ratio = "{0:6.2f}".format(time_2 / time_1)

            if util.is_na(time_1) and util.is_na(time_2):
                color = 'red'
                mark = ' '
            elif util.is_na(time_1) and not util.is_na(time_2):
                color = 'green'
                mark = '-'
            elif not util.is_na(time_1) and util.is_na(time_2):
                color = 'red'
                mark = '!'
            elif time_2 < time_1 / factor:
                color = 'green'
                mark = '-'
            elif time_2 > time_1 * factor:
                color = 'red'
                mark = '+'
            else:
                color = 'default'
                mark = ' '
            details = "{0:1s} {1:>9s}  {2:>9s} {3:>9s}  ".format(
                mark,
                human_value(time_1, "seconds"),
                human_value(time_2, "seconds"),
                ratio)

            if split:
                bench[color].append((color, details, benchmark))
            else:
                bench['all'].append((color, details, benchmark))

        if split:
            keys = ['green', 'default', 'red']
        else:
            keys = ['all']

        titles = {}
        titles['green'] = "Benchmarks that have improved:"
        titles['default'] = "Benchmarks that have stayed the same:"
        titles['red'] = "Benchmarks that have got worse:"
        titles['all'] = "All benchmarks:"

        for key in keys:

            if len(bench[key]) == 0:
                continue

            print("")
            print(titles[key])
            print("")
            print("    before     after       ratio")
            print("  [{0:8s}] [{1:8s}]".format(hash_1[:8], hash_2[:8]))

            for color, details, benchmark in bench[key]:
                color_print(details, color, end='')
                print(benchmark)
