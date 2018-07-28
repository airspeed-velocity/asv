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
from .. import statistics

from . import common_args


def mean(values):
    if all([value is None for value in values]):
        return None
    else:
        values = [value for value in values if value is not None]
        return sum(values) / float(len(values))


def unroll_result(benchmark_name, params, *values):
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
    num_comb = 1
    for p in params:
        num_comb *= len(p)

    values = list(values)
    for j in range(len(values)):
        if values[j] is None:
            values[j] = [None] * num_comb

    for params, value in zip(itertools.product(*params), zip(*values)):
        if params == ():
            name = benchmark_name
        else:
            name = "%s(%s)" % (benchmark_name, ", ".join(params))
        yield (name,) + value


def _isna(value):
    # None (failed) or NaN (skipped)
    return value is None or value != value


def _is_result_better(a, b, a_stats, b_stats, factor, use_stats=True):
    """
    Check if result 'a' is better than 'b' by the given factor,
    possibly taking confidence intervals into account.

    """

    if use_stats and a_stats and b_stats:
        # Return False if estimates don't differ
        if not statistics.is_different(a_stats, b_stats):
            return False

    return a < b / factor


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
                    sort_by_ratio=False, only_changed=False, use_stats=True):
        return print_table(conf, hash_1, hash_2, factor, split,
                           resultset_1, resultset_2, machine,
                           sort_by_ratio, only_changed, use_stats)


def print_table(conf, hash_1, hash_2, factor, split,
                resultset_1=None, resultset_2=None, machine=None,
                sort_by_ratio=False, only_changed=False, use_stats=True):
    results_1 = {}
    results_2 = {}
    stats_1 = {}
    stats_2 = {}
    versions_1 = {}
    versions_2 = {}

    def results_default_iter(commit_hash):
        for result in iter_results_for_machine_and_hash(
                conf.results_dir, machine, commit_hash):
            for key in result.get_all_result_keys():
                params = result.get_result_params(key)
                result_value = result.get_result_value(key, params)
                result_stats = result.get_result_stats(key, params)
                result_version = result.benchmark_version.get(key)
                yield key, params, result_value, result_stats, result_version

    if resultset_1 is None:
        resultset_1 = results_default_iter(hash_1)

    if resultset_2 is None:
        resultset_2 = results_default_iter(hash_2)

    for key, params, value, stats, version in resultset_1:
        for name, value, stats in unroll_result(key, params, value, stats):
            results_1[name] = value
            stats_1[name] = stats
            versions_1[name] = version

    for key, params, value, stats, version in resultset_2:
        for name, value, stats in unroll_result(key, params, value, stats):
            results_2[name] = value
            stats_2[name] = stats
            versions_2[name] = version

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
        bench['lightgrey'] = []
        bench['default'] = []
    else:
        bench['all'] = []

    worsened = False
    improved = False

    for benchmark in joint_benchmarks:
        if benchmark in results_1:
            time_1 = results_1[benchmark]
        else:
            time_1 = float("nan")

        if benchmark in results_2:
            time_2 = results_2[benchmark]
        else:
            time_2 = float("nan")

        if benchmark in stats_1 and stats_1[benchmark]:
            err_1 = statistics.get_err(time_1, stats_1[benchmark])
        else:
            err_1 = None

        if benchmark in stats_2 and stats_2[benchmark]:
            err_2 = statistics.get_err(time_2, stats_2[benchmark])
        else:
            err_2 = None

        version_1 = versions_1.get(benchmark)
        version_2 = versions_2.get(benchmark)

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

        if (version_1 is not None and version_2 is not None and
                version_1 != version_2):
            # not comparable
            color = 'lightgrey'
            mark = 'x'
        elif time_1 is not None and time_2 is None:
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
        elif _is_result_better(time_2, time_1,
                               stats_2.get(benchmark), stats_1.get(benchmark),
                               factor, use_stats=use_stats):
            color = 'green'
            mark = '-'
            improved = True
        elif _is_result_better(time_1, time_2,
                               stats_1.get(benchmark), stats_2.get(benchmark),
                               factor, use_stats=use_stats):
            color = 'red'
            mark = '+'
            worsened = True
        else:
            color = 'default'
            mark = ' '

            # Mark statistically insignificant results
            if (_is_result_better(time_1, time_2, None, None, factor) or
                    _is_result_better(time_2, time_1, None, None, factor)):
                ratio = "~" + ratio.strip()

        if only_changed and mark in (' ', 'x'):
            continue

        details = "{0:1s} {1:>15s}  {2:>15s} {3:>8s}  ".format(
            mark,
            human_value(time_1, "seconds", err=err_1),
            human_value(time_2, "seconds", err=err_2),
            ratio)

        if split:
            bench[color].append((color, details, benchmark, ratio_num))
        else:
            bench['all'].append((color, details, benchmark, ratio_num))

    if split:
        keys = ['green', 'default', 'red', 'lightgrey']
    else:
        keys = ['all']

    titles = {}
    titles['green'] = "Benchmarks that have improved:"
    titles['default'] = "Benchmarks that have stayed the same:"
    titles['red'] = "Benchmarks that have got worse:"
    titles['lightgrey'] = "Benchmarks that are not comparable:"
    titles['all'] = "All benchmarks:"

    for key in keys:

        if len(bench[key]) == 0:
            continue

        if not only_changed:
            color_print("")
            color_print(titles[key])
            color_print("")
        color_print("       before           after         ratio")
        color_print("     [{0:8s}]       [{1:8s}]".format(hash_1[:8], hash_2[:8]))

        if sort_by_ratio:
            bench[key].sort(key=lambda v: v[3], reverse=True)

        for color, details, benchmark, ratio in bench[key]:
            color_print(details, color, end='')
            color_print(benchmark)

    return worsened, improved
