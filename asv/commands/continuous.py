# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import six

from . import Command
from .run import Run
from .compare import Compare

from ..repo import get_repo
from ..console import color_print
from .. import results

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

        def results_iter(commit_hash):
            for env in run_objs['environments']:
                filename = results.get_filename(
                    run_objs['machine_params']['machine'], commit_hash, env.name)
                filename = os.path.join(conf.results_dir, filename)
                result = results.Results.load(filename)
                for name, benchmark in six.iteritems(run_objs['benchmarks']):
                    yield name, result.results.get(name, float("nan"))

        status = Compare.print_table(conf, parent, head,
                                     resultset_1=results_iter(parent),
                                     resultset_2=results_iter(head),
                                     factor=factor, split=False, only_changed=True,
                                     sort_by_ratio=True)
        worsened, improved = status

        if worsened:
            color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'red')
        elif improved:
            color_print("SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY.\n", 'green')
        else:
            color_print("BENCHMARKS NOT SIGNIFICANTLY CHANGED.\n", 'green')

        return worsened
