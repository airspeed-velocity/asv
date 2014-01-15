# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import multiprocessing
import os

import six

from ..benchmarks import Benchmarks
from ..config import Config
from ..console import console
from ..machine import Machine
from ..repo import get_repo
from ..results import Results, find_latest_result_hash, get_existing_hashes
from .. import util

from .setup import Setup


def _do_build(args):
    env, conf = args
    env.uninstall(conf.project)
    try:
        env.install(os.path.abspath(conf.project), editable=True)
    except util.ProcessError:
        return False
    return True


def _do_build_multiprocess(args):
    """
    multiprocessing callback to build the project in one particular
    environment.
    """
    try:
        return _do_build(args)
    except:
        import traceback
        traceback.format_exc()
        raise


class Run(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "run", help="Run a benchmark suite",
            description="Run a benchmark suite.")

        parser.add_argument(
            'range', nargs=1,
            help="""Range of commits to benchmark.  By default, this
            is passed as the first argument to ``git log``.  See
            'specifying ranges' section of the `gitrevisions` manpage
            for more info.  Also accepts the special values 'latest',
            and 'existing'.  'latest' will benchmark all commits since
            the latest benchmarked on this machine.  'existing' will
            benchmark against all commits for which there are existing
            benchmarks on any machine.""")
        parser.add_argument(
            "--steps", "-s", type=int, default=0,
            help="""Maximum number of steps to benchmark.  This is
            used to subsample the commits determined by --range or
            --latest to a reasonable number.""")
        parser.add_argument(
            "--bench", "-b", type=str, nargs="*",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
            help="""Build (but don't benchmark) in parallel.  The
            value is the number of CPUs to use, or if no number
            provided, use the number of cores on this machine.  NOTE:
            parallel building is still experimental and may not work
            in all cases.""")
        parser.add_argument(
            "--show-exc", "-e", action="store_true",
            help="""When provided, display the exceptions from the
            benchmarks when they fail.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        conf = Config.load(args.config)
        return cls.run(
            conf=conf, range_spec=args.range[0], steps=args.steps,
            bench=args.bench, parallel=args.parallel,
            show_exc=args.show_exc
        )

    @classmethod
    def run(cls, conf, range_spec="master^!", steps=0, bench=None, parallel=-1,
            show_exc=False):
        params = {}
        machine_params = Machine.load(interactive=True)
        params.update(machine_params.__dict__)
        machine_params.save(conf.results_dir)

        repo = get_repo(conf.repo, conf.project)

        if range_spec == 'existing':
            commit_hashes = [h for h, d in get_existing_hashes(
                conf.results_dir)]
            range_spec = None
        elif range_spec == 'latest':
            latest_result = find_latest_result_hash(
                machine_params.machine, conf.results_dir)
            # TODO: This is shamelessly git-specific
            range_spec = '{0}..master'.format(latest_result)

        if range_spec is not None:
            commit_hashes = repo.get_hashes_from_range(range_spec)

        if len(commit_hashes) == 0:
            console.message("No commit hashes selected", "yellow")
            return

        if steps > 0:
            spacing = int(len(commit_hashes) / steps) or 1
            commit_hashes = [commit_hashes[i] for i in
                             six.moves.xrange(0, len(commit_hashes), spacing)]

        environments = Setup.run(conf=conf, parallel=parallel)
        if len(environments) == 0:
            console.message("No environments selected", "yellow")
            return

        benchmarks = Benchmarks(conf, regex=bench)
        if len(benchmarks) == 0:
            console.message("No benchmarks selected", "yellow")
            return
        benchmarks.save()

        steps = len(commit_hashes) * len(benchmarks) * len(environments)

        console.message(
            "Running {0} total benchmarks "
            "({1} commits * {2} environments * {3} benchmarks)".format(
                steps, len(commit_hashes),
                len(environments), len(benchmarks)), "green")
        console.set_nitems(steps)

        if parallel <= 0:
            parallel = multiprocessing.cpu_count()

        for commit_hash in commit_hashes:
            with console.group(
                    "{0} commit hash {1}:".format(
                        conf.project, commit_hash[:8]), 'green'):
                repo.checkout(commit_hash)
                repo.clean()

                for subenv in util.iter_chunks(environments, parallel):
                    with console.group(
                            "Building for {0}".format(
                                ', '.join([x.name for x in subenv])), "green"):
                        args = [(env, conf) for env in subenv]
                        if parallel != 1:
                            pool = multiprocessing.Pool(parallel)
                            successes = pool.map(_do_build_multiprocess, args)
                            pool.close()
                        else:
                            successes = map(_do_build, args)

                    for env, success in zip(subenv, successes):
                        config_name = env.name

                        with console.group("Benchmarking " + config_name, "green"):
                            if success:
                                params['python'] = env.python
                                params.update(env.requirements)

                                with console.indent():
                                    times = benchmarks.run_benchmarks(
                                        env, show_exc=show_exc)
                            else:
                                console.add(" can't install.  skipping", "yellow")
                                with console.indent():
                                    times = benchmarks.skip_benchmarks()

                            result = Results(
                                params,
                                env,
                                commit_hash,
                                repo.get_date(commit_hash))

                            result.add_times(times)

                            result.save(conf.results_dir)

        console.message('')
