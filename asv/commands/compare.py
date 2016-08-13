# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
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


def _isna(value):
    # None (failed) or NaN (skipped)
    return value is None or value != value


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
    def run(cls, conf, hash_1, hash_2, factor=None, split=False, machine=None):

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

        cls.print_table(conf, hash_1, hash_2, factor=factor, machine=machine,
                        split=split)

    @classmethod
    def print_table(cls, conf, hash_1, hash_2, factor, split,
                    resultset_1=None, resultset_2=None, machine=None,
                    sort_by_ratio=False, only_changed=False):
        results_1 = {}
        results_2 = {}

        def results_default_iter(commit_hash):
            for result in iter_results_for_machine_and_hash(
                    conf.results_dir, machine, commit_hash):
                for key, value in six.iteritems(result.results):
                    yield key, value

        if resultset_1 is None:
            resultset_1 = results_default_iter(hash_1)

        if resultset_2 is None:
            resultset_2 = results_default_iter(hash_2)

        for key, result in resultset_1:
            for name, value in unroll_result(key, result):
                if name not in results_1:
                    results_1[name] = []
                results_1[name].append(value)

        for key, result in resultset_2:
            for name, value in unroll_result(key, result):
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

        joint_benchmarks = sorted(list(benchmarks_1 | benchmarks_2))

        bench = {}

        if split:
            bench['green'] = []
            bench['red'] = []
            bench['default'] = []
        else:
            bench['all'] = []

        worsened = False
        improved = False

        for benchmark in joint_benchmarks:
            if benchmark in results_1:
                time_1 = mean(results_1[benchmark])
            else:
                time_1 = float("nan")

            if benchmark in results_2:
                time_2 = mean(results_2[benchmark])
            else:
                time_2 = float("nan")

            if _isna(time_1) or _isna(time_2):
                ratio = 'n/a'
                ratio_num = 1e9
            else:
                try:
                    ratio_num = time_2 / time_1
                    ratio = "{0:6.2f}".format(ratio_num)
                except ZeroDivisionError:
                    ratio_num = 1e9
                    ratio = "n/a"

            if time_1 is not None and time_2 is None:
                # introduced a failure
                color = 'red'
                mark = '!'
                worsened = True
            elif time_1 is None and time_2 is not None:
                # fixed a failure
                color = 'green'
                mark = ' '
                improved = True
            elif time_1 is None and time_2 is None:
                # both failed
                color = 'red'
                mark = ' '
            elif _isna(time_1) or _isna(time_2):
                # either one was skipped
                color = 'default'
                mark = ' '
            elif time_2 < time_1 / factor:
                color = 'green'
                mark = '-'
                improved = True
            elif time_2 > time_1 * factor:
                color = 'red'
                mark = '+'
                worsened = True
            else:
                color = 'default'
                mark = ' '

            if only_changed and mark == ' ':
                continue

            details = "{0:1s} {1:>9s}  {2:>9s} {3:>9s}  ".format(
                mark,
                human_value(time_1, "seconds"),
                human_value(time_2, "seconds"),
                ratio)

            if split:
                bench[color].append((color, details, benchmark, ratio_num))
            else:
                bench['all'].append((color, details, benchmark, ratio_num))

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

            if not only_changed:
                color_print("")
                color_print(titles[key])
                color_print("")
            color_print("    before     after       ratio")
            color_print("  [{0:8s}] [{1:8s}]".format(hash_1[:8], hash_2[:8]))

            if sort_by_ratio:
                bench[key].sort(key=lambda v: v[3], reverse=True)

            for color, details, benchmark, ratio in bench[key]:
                color_print(details, color, end='')
                color_print(benchmark)

        return worsened, improved
