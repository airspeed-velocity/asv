# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from . import Command
from ..machine import iter_machine_files
from ..results import iter_results_for_machine_and_hash
from ..util import human_time, load_json
from ..console import color_print


def mean(values):
    if all([value is None for value in values]):
        return None
    else:
        values = [value for value in values if value is not None]
        return sum(values) / float(len(values))


class Compare(Command):

    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "compare",
            help="""Compare the benchmark results between two revisions
                    (averaged over configurations)""",
            description="Compare two sets of results")

        parser.add_argument(
            'revision1', nargs=1,
            help="""The reference revision.""")

        parser.add_argument(
            'revision2', nargs=1,
            help="""The revision being compared""")

        parser.add_argument(
            '--threshold', '-t', nargs='?', type=float, default=2,
            help="""The threshold to use to color-code divergent results. This
                    is a factor, so for example setting this to 2 will
                    highlight all results differing by more than a factor of
                    2.""")

        parser.add_argument(
           '--split', '-s', action='store_true',
           help="""Split the output into a table of benchmarks that have
           improved, stayed the same, and gotten worse""")

        parser.add_argument(
            '--machine', '-m', nargs='?', type=str, default=None,
            help="""The machine to compare the revisions for""")


        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf,
                       hash_1=args.revision1[0],
                       hash_2=args.revision2[0],
                       threshold=args.threshold, split=args.split,
                       machine=args.machine)

    @classmethod
    def run(cls, conf, hash_1, hash_2, threshold=2, split=False, machine=None):

        machines = []
        for path in iter_machine_files(conf.results_dir):
            d = load_json(path)
            machines.append(d['machine'])

        if len(machines) == 0:
            raise Exception("No results found")
        elif machine is None:
            if len(machines) > 1:
                raise Exception("Results available for several machines: {0} - "
                                "specify which one to use with the --machine option".format('/'.join(machines)))
            else:
                machine = machines[0]
        elif not machine in machines:
            raise ValueError("Results for machine '{0} not found".format(machine))

        results_1 = {}
        results_2 = {}

        for result in iter_results_for_machine_and_hash(
                conf.results_dir, machine, hash_1):
            for key in result.results:
                if key not in results_1:
                    results_1[key] = []
                results_1[key].append(result.results[key])

        for result in iter_results_for_machine_and_hash(
                conf.results_dir, machine, hash_2):
            for key in result.results:
                if key not in results_2:
                    results_2[key] = []
                results_2[key].append(result.results[key])

        if len(results_1) == 0:
            raise ValueError("Did not find results for commit {0}".format(hash_1))

        if len(results_2) == 0:
            raise ValueError("Did not find results for commit {0}".format(hash_2))

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

            if time_1 is None or time_2 is None:
                ratio = 'n/a'
            else:
                ratio = "{0:6.2f}".format(time_2 / time_1)

            if time_1 is None and time_2 is None:
                color = 'red'
            elif time_1 is None and time_2 is not None:
                color = 'green'
                mark = '-'
            elif time_1 is not None and time_2 is None:
                color = 'red'
                mark = '!'
            elif time_2 < time_1 / threshold:
                color = 'green'
                mark = '-'
            elif time_2 > time_1 * threshold:
                color = 'red'
                mark = '+'
            else:
                color = 'default'
                mark = ' '
            details = "{0:1s} {1:>9s}  {2:>9s} {3:>9s}  ".format(
                mark,
                'failed' if time_1 is None else human_time(time_1),
                'failed' if time_2 is None else human_time(time_2),
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
