# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import ast

from ..benchmarks import Benchmarks
from ..machine import iter_machine_files
from ..repo import get_repo, NoSuchNameError
from ..util import load_json
from ..environment import get_environments
from .. import util

from . import common_args
from .compare import Compare, unroll_result, results_default_iter, format_benchmark_name


class CompareVariant(Compare):

    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "compare_variant",
            help="""Compare the benchmark results between two variants for the same revision
                    (averaged over configurations)""",
            description="Compare two sets of results")

        parser.add_argument(
            'revision1',
            help="""The reference revision.""")

        parser.add_argument(
            'variant1',
            help="""The first variant being compared.""")

        parser.add_argument(
            'variant2',
            help="""The second variant being compared.""")

        common_args.add_compare(parser, sort_default='name', only_changed_default=False)

        parser.add_argument(
            '--machine', '-m', type=str, default=None,
            help="""The machine to compare the revisions for.""")

        common_args.add_environment(parser)

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf,
                       hash_1=args.revision1,
                       variant_1=args.variant1,
                       variant_2=args.variant2,
                       factor=args.factor, split=args.split,
                       only_changed=args.only_changed, sort=args.sort,
                       machine=args.machine,
                       env_spec=args.env_spec)

    @classmethod
    def run(cls, conf, hash_1, variant_1, variant_2, factor=None, split=False, only_changed=False,
            sort='name', machine=None, env_spec=None):

        repo = get_repo(conf)
        try:
            hash_1 = repo.get_hash_from_name(hash_1)
        except NoSuchNameError:
            pass

        if env_spec:
            env_names = ([env.name for env in get_environments(conf, env_spec, verbose=False)]
                         + list(env_spec))
        else:
            env_names = None

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

        commit_names = {hash_1: repo.get_name_from_hash(hash_1)}

        cls.print_table(conf, hash_1, variant_1, variant_2, factor=factor, split=split,
                        only_changed=only_changed, sort=sort,
                        machine=machine, env_names=env_names, commit_names=commit_names)

    @classmethod
    def print_table(cls, conf, hash_1, variant_1, variant_2, factor, split,
                    resultset_1=None, resultset_2=None, machine=None,
                    only_changed=False, sort='name', use_stats=True, env_names=None,
                    commit_names=None):
        results_1 = {}
        results_2 = {}
        ss_1 = {}
        ss_2 = {}
        versions_1 = {}
        versions_2 = {}
        units = {}

        benchmarks = Benchmarks.load(conf)

        if commit_names is None:
            commit_names = {}

        if resultset_1 is None:
            resultset_1 = results_default_iter(hash_1, conf, machine, env_names)

        machine_env_names = set()

        # Transform the variant to match version in results
        # The variant format is done at the end of `Benchmark.__init__`
        variant_1 = ast.literal_eval(variant_1)
        variant_2 = ast.literal_eval(variant_2)
        variant_1 = repr(variant_1)
        variant_2 = repr(variant_2)

        for key, params, value, stats, samples, version, machine, env_name in resultset_1:
            machine_env_name = "{}/{}".format(machine, env_name)
            machine_env_names.add(machine_env_name)

            # Get values for variant 1
            for v1_name_parts, v1_value, v1_stats, v2_samples in unroll_result(key, params, value, stats, samples):

                if variant_1 not in v1_name_parts:
                    continue

                # Replace the variant values in the name to have the same name in both resultsets
                v1_name_parts[v1_name_parts.index(variant_1)] = "VARIANT"

                v1_name = format_benchmark_name(v1_name_parts)

                units[(v1_name, machine_env_name)] = benchmarks.get(key, {}).get('unit')
                results_1[(v1_name, machine_env_name)] = v1_value
                ss_1[(v1_name, machine_env_name)] = (v1_stats, v2_samples)
                versions_1[(v1_name, machine_env_name)] = version

            # Get values for variant 2
            for v2_name_parts, v2_value, v2_stats, v2_samples in unroll_result(key, params, value, stats, samples):

                if variant_2 not in v2_name_parts:
                    continue

                # Replace the variant values in the name to have the same name in both resultsets
                v2_name_parts[v2_name_parts.index(variant_2)] = "VARIANT"

                v2_name = format_benchmark_name(v2_name_parts)

                units[(v2_name, machine_env_name)] = benchmarks.get(key, {}).get('unit')
                results_2[(v2_name, machine_env_name)] = v2_value
                ss_2[(v2_name, machine_env_name)] = (v2_stats, v2_samples)
                versions_2[(v2_name, machine_env_name)] = version

        if len(results_1) == 0:
            raise util.UserError(
                "Did not find results for commit {0} and variant {1}".format(hash_1, variant_1))

        if len(results_2) == 0:
            raise util.UserError(
                "Did not find results for commit {0} and variant {1}".format(hash_1, variant_2))

        bench, worsened, improved = cls.dispatch_results(
            results_1,
            results_2,
            units,
            split,
            ss_1,
            ss_2,
            versions_1,
            versions_2,
            factor,
            use_stats,
            only_changed,
        )

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

        # Compute headers
        for key in keys:

            if len(bench[key]) == 0:
                continue

            header = []

            if not only_changed:
                header.append("")
                header.append(titles[key])
                header.append("")

            header.append("variant 1: {0:s}".format(variant_1))
            header.append("variant 2: {0:s}".format(variant_2))
            header.append("")
            header.append("       before           after         ratio")
            header.append("     [{0:8s}]       [{1:8s}]".format("variant1", "variant2"))

            name_1 = commit_names.get(hash_1)
            if name_1:
                name_1 = '<{0}>'.format(name_1)
            else:
                name_1 = ''

            if name_1:
                header.append("     {0:10s}".format(name_1))

            cls.display_result(bench, key, sort, header, machine_env_names)

        return worsened, improved
