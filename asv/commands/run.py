# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six

from ..benchmarks import Benchmarks
from ..config import Config
from ..console import console
from ..machine import Machine
from ..repo import get_repo
from ..results import Results
from .. import util

from .setup import Setup


class Run(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "run", help="Run a benchmark suite",
            description="Run a benchmark suite.")

        parser.add_argument(
            "--range", "-r", default="master^!",
            help="""Range of commits to benchmark.  This is passed as
            the first argument to ``git log``.  See 'specifying
            ranges' section of the `gitrevisions` manpage for more
            info.  Default: master only""")
        parser.add_argument(
            "--steps", "-s", type=int, default=0,
            help="""Maximum number of steps to benchmark.  This is
            used to subsample the commits determined by --range to a
            reasonable number.""")
        parser.add_argument(
            "--bench", "-b", type=str, nargs="*",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        conf = Config.load(args.config)
        return cls.run(
            conf=conf, range=args.range, steps=args.steps, bench=args.bench)

    @classmethod
    def run(cls, conf, range="master^!", steps=0, bench=None):
        params = {}
        machine_params = Machine.load()
        params.update(machine_params.__dict__)
        machine_params.save(conf.results_dir)

        benchmarks = Benchmarks(conf.benchmark_dir, bench=bench)
        if len(benchmarks) == 0:
            console.message("No benchmarks selected", "yellow")
            return

        repo = get_repo(conf.repo, conf.project)
        commit_hashes = repo.get_hashes_from_range(range)
        if steps > 0:
            subhashes = []
            for i in six.moves.xrange(0, len(commit_hashes),
                                      int(len(commit_hashes) / steps)):
                subhashes.append(commit_hashes[i])
            commit_hashes = subhashes
        if len(commit_hashes) == 0:
            console.message("No commit hashes selected", "yellow")
            return

        environments = Setup.run(conf=conf)
        if len(environments) == 0:
            console.message("No environments selected", "yellow")
            return

        steps = len(commit_hashes) * len(benchmarks) * len(environments)

        console.message(
            "Running {0} total benchmarks ({1} commits * {2} environments * {3} benchmarks)".format(
                steps, len(commit_hashes), len(environments), len(benchmarks)), "green")
        console.set_nitems(steps)

        for env in environments:
            config_name = env.name
            params['python'] = env.python
            params.update(env.requirements)

            with console.group("Benchmarking " + config_name, "green"):
                for commit_hash in commit_hashes:
                    with console.group(
                            "{0} commit hash {1}:".format(
                                conf.project, commit_hash[:8]), 'green'):
                        result = Results(
                            params,
                            env,
                            commit_hash,
                            repo.get_date(commit_hash))

                        repo.clean()
                        repo.checkout(commit_hash)
                        env.uninstall(conf.project)
                        try:
                            env.install(os.path.abspath(conf.project))
                        except util.ProcessError:
                            console.add(" can't install.  skipping", "yellow")
                            with console.indent():
                                times = benchmarks.skip_benchmarks()
                        else:
                            with console.indent():
                                times = benchmarks.run_benchmarks(env)

                        result.add_times(times)

                        result.save(conf.results_dir)

        console.message('')
