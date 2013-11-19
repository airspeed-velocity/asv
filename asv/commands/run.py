# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

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

        # TODO: Range of branches
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

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        conf = Config.from_file(args.config)
        return cls.run(
            conf=conf, range=args.range, steps=args.steps)

    @classmethod
    def run(cls, conf, range="master^!", steps=0):
        params = {}
        machine_params = Machine.load_machine_file()
        params.update(machine_params.__dict__)
        machine_params.save_machine_file(conf.results_dir)

        environments = Setup.run(conf=conf)

        repo = get_repo(conf.repo, conf.project)
        commit_hashes = repo.get_hashes_from_range(range)
        if steps > 0:
            subhashes = []
            for i in range(0, len(commit_hashes),
                           int(len(commit_hashes) / steps)):
                subhashes.append(commit_hashes[i])
            commit_hashes = subhashes

        benchmarks = Benchmarks(conf.benchmark_dir)

        steps = len(commit_hashes) * len(benchmarks) * len(environments)

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
