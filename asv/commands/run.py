# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import subprocess

from ..benchmarks import Benchmarks
from ..config import Config
from ..console import console
from ..machine import Machine
from ..repo import Repo
from ..results import Results

from .setup import Setup


class Run(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser("run", help="Run a benchmark suite")

        # TODO: Range of branches
        parser.add_argument(
            "--range", "-r", default="master^!",
            help="Range of commits to test.  This is passed as the first "
            "argument to `git log`.  See 'specifying ranges' section "
            "of the gitrevisions manpage for more info.  Default: master only")
        parser.add_argument(
            "--steps", "-s", type=int, default=0,
            help="Maximum number of steps to test.  This is used to subsample "
            "the commits determined by --range to a reasonable number.")
        parser.add_argument(
            "--redo", action="store_true",
            help="Redo all benchmarks, even if they've already been "
            "done for a particular configuration.")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        environments = Setup.run(args)

        conf = Config.from_file(args.config)

        params = {}
        machine_params = Machine()
        params.update(machine_params.__dict__)
        machine_params.copy_machine_file(conf.results_dir)

        repo = Repo(conf.repo, conf.package)
        githashes = repo.get_hashes_from_range(args.range)
        if args.steps > 0:
            subhashes = []
            for i in range(0, len(githashes), int(len(githashes) / args.steps)):
                subhashes.append(githashes[i])
            githashes = subhashes

        benchmarks = Benchmarks(conf.benchmark_dir)

        steps = len(githashes) * len(benchmarks) * len(environments)

        console.set_nitems(steps)

        for env in environments:
            config_name = env.name
            params['python'] = env.python
            params.update(env.requirements)

            with console.group("Benchmarking " + config_name, "green"):
                for githash in githashes:
                    with console.group(
                            "{0} githash {1}:".format(
                                conf.package, githash[:8]), 'green'):
                        result = Results(
                            params,
                            env.python,
                            env.requirements,
                            githash,
                            repo.get_date(githash))
                        if not args.redo and os.path.exists(
                                os.path.join(conf.results_dir, result.filename)):
                            console.add(" already done.  skipping", "yellow")
                            console.fake_steps(len(benchmarks))
                            continue

                        repo.clean()
                        repo.checkout(githash)
                        env.uninstall(conf.package)
                        try:
                            env.install(os.path.abspath(conf.package))
                        except subprocess.CalledProcessError:
                            console.add(" can't install.  skipping", "yellow")
                            console.fake_steps(len(benchmarks))
                            continue

                        with console.indent():
                            times = benchmarks.run_benchmarks(env)

                        result.add_times(times)

                        result.save(conf.results_dir)

        console.message('')
