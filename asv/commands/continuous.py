# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import six

from . import Command
from .run import Run
from .compare import print_table

from ..repo import get_repo
from ..console import color_print, log
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
            help="""The commit/branch to test. By default, the first configured branch.""")
        parser.add_argument(
            "--record-samples", action="store_true",
            help="""Store raw measurement samples, not only statistics""")
        parser.add_argument(
            "--quick", "-q", action="store_true",
            help="""Do a "quick" run, where each benchmark function is
            run only once.  This is useful to find basic errors in the
            benchmark functions faster.  The results are unlikely to
            be useful, and thus are not saved.""")
        common_args.add_factor(parser)
        common_args.add_show_stderr(parser)
        common_args.add_bench(parser)
        common_args.add_machine(parser)
        common_args.add_environment(parser)
        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args, **kwargs):
        return cls.run(
            conf=conf, branch=args.branch, base=args.base, factor=args.factor,
            show_stderr=args.show_stderr, bench=args.bench, machine=args.machine,
            env_spec=args.env_spec, record_samples=args.record_samples,
            quick=args.quick, **kwargs
        )

    @classmethod
    def run(cls, conf, branch=None, base=None, factor=None, show_stderr=False, bench=None,
            machine=None, env_spec=None, record_samples=False, quick=False, _machine_file=None):
        repo = get_repo(conf)
        repo.pull()

        if branch is None:
            branch = conf.branches[0]
        head = repo.get_hash_from_name(branch)

        if base is None:
            parent = repo.get_hash_from_parent(head)
        else:
            parent = repo.get_hash_from_name(base)

        commit_hashes = [head, parent]
        run_objs = {}

        result = Run.run(
            conf, range_spec=commit_hashes, bench=bench,
            show_stderr=show_stderr, machine=machine, env_spec=env_spec,
            record_samples=record_samples, quick=quick,
            _returns=run_objs, _machine_file=_machine_file)
        if result:
            return result

        status = print_table(conf, parent, head,
                             resultset_1=_results_iter(parent, run_objs, result),
                             resultset_2=_results_iter(head, run_objs, result),
                             factor=factor, split=False, only_changed=True,
                             sort_by_ratio=True)
        worsened, improved = status

        color_print("")
        if worsened:
            color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.", 'red')
        elif improved:
            color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.", 'green')
        else:
            color_print("BENCHMARKS NOT SIGNIFICANTLY CHANGED.", 'green')

        return worsened


def _results_iter(commit_hash, run_objs, result):
    """
    Iterate over results for the given commit_hash.

    Parameters
    ----------
    commit_hash : str
    run_objs : dict
    result : results.Results

    Yields
    ------
    name : str
    params : list
    value : object
    stats : list
    version : str
    """
    for env in run_objs['environments']:
        machine_name = run_objs['machine_params']['machine']
        filename = results.get_filename(machine_name, commit_hash, env.name)
        filename = os.path.join(conf.results_dir, filename)
        try:
            result = results.Results.load(filename, machine_name)
        except util.UserError as err:
            log.warn(six.text_type(err))
            continue

        for name, benchmark in six.iteritems(run_objs['benchmarks']):
            params = benchmark['params']
            version = benchmark['version']

            value = result.get_result_value(name, params)
            stats = result.get_result_stats(name, params)
            yield name, params, value, stats, version
