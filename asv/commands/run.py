# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

import logging

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..machine import Machine
from ..repo import get_repo
from ..results import Results, find_latest_result_hash, get_existing_hashes
from .. import util

from .setup import Setup


def _do_build(args):
    env, conf, commit_hash = args
    try:
        with log.set_level(logging.WARN):
            env.repo.checkout(commit_hash)
            env.install_project(conf, silent=True)
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


class Run(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "run", help="Run a benchmark suite",
            description="Run a benchmark suite.")

        parser.add_argument(
            'range', nargs='?', default="master",
            help="""Range of commits to benchmark.  For a git
            repository, this is passed as the first argument to ``git
            log``.  See 'specifying ranges' section of the
            `gitrevisions` manpage for more info.  Also accepts the
            special values 'NEW', 'ALL', 'MISSING', and
            'EXISTING'. 'NEW' will benchmark all commits since the
            latest benchmarked on this machine.  'ALL' will benchmark
            all commits in the project. 'MISSING' will benchmark all
            commits in the project's history that have not yet been
            benchmarked. 'EXISTING' will benchmark against all commits
            for which there are existing benchmarks on any machine. By
            default, will benchmark the head of the current master
            branch.""")
        parser.add_argument(
            "--steps", "-s", type=int, default=0,
            help="""Maximum number of steps to benchmark.  This is
            used to subsample the commits determined by range to a
            reasonable number.""")
        parser.add_argument(
            "--bench", "-b", type=str, nargs="?",
            help="""Regular expression(s) for benchmark to run.  When
            not provided, all benchmarks are run.""")
        parser.add_argument(
            "--profile", "-p", action="store_true",
            help="""In addition to timing, run the benchmarks through
            the `cProfile` profiler and store the results.""")
        parser.add_argument(
            "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
            help="""Build (but don't benchmark) in parallel.  The
            value is the number of CPUs to use, or if no number
            provided, use the number of cores on this machine.""")
        parser.add_argument(
            "--show-stderr", "-e", action="store_true",
            help="""Display the stderr output from the benchmarks.""")
        parser.add_argument(
            "--quick", "-q", action="store_true",
            help="""Do a "quick" run, where each benchmark function is
            run only once.  This is useful to find basic errors in the
            benchmark functions faster.  The results are unlikely to
            be useful, and thus are not saved.""")
        parser.add_argument(
            "--python", nargs='?', type=str,
            default=None,
            help="""Specify a Python interpreter in which to run the
            benchmarks.  It may be an executable to be searched for on
            the $PATH, an absolute path, or the special value "same"
            which will use the same Python interpreter that asv is
            using.  This interpreter must have the benchmarked project
            already installed, including its dependencies, and a specific
            revision of the benchmarked project may not be provided.

            It may also be any string accepted by any of the
            environment plugins.  For example, the conda plugin
            accepts "2.7" to mean create a new Conda environment with
            Python version 2.7.""")
        parser.add_argument(
            "--dry-run", "-n", action="store_true",
            default=None,
            help="""Do not save any results to disk.""")
        parser.add_argument(
            "--machine", "-m", nargs='?', type=str, default=None,
            help="""Use the given name to retrieve machine
            information.  If not provided, the hostname is used.  If
            that is not found, and there is only one entry in
            ~/.asv-machine.json, that one entry will be used.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(
            conf=conf, range_spec=args.range, steps=args.steps,
            bench=args.bench, parallel=args.parallel,
            show_stderr=args.show_stderr, quick=args.quick,
            profile=args.profile, python=args.python,
            dry_run=args.dry_run, machine=args.machine
        )

    @classmethod
    def run(cls, conf, range_spec="master", steps=0, bench=None, parallel=1,
            show_stderr=False, quick=False, profile=False, python=None,
            dry_run=False, machine=None, _machine_file=None,
            _returns={}):
        params = {}
        machine_params = Machine.load(
            machine_name=machine,
            _path=_machine_file, interactive=True)
        params.update(machine_params.__dict__)
        machine_params.save(conf.results_dir)

        repo = get_repo(conf)

        if python is not None:
            conf.pythons = [python]
        else:
            repo.pull()

        if range_spec == 'EXISTING':
            commit_hashes = [h for h, d in get_existing_hashes(
                conf.results_dir)]
            range_spec = None
        elif range_spec == 'NEW':
            latest_result = find_latest_result_hash(
                machine_params.machine, conf.results_dir)
            # TODO: This is shamelessly git-specific
            range_spec = '{0}..master'.format(latest_result)
        elif range_spec == "ALL":
            range_spec = ""
        elif range_spec == "MISSING":
            commit_hashes = repo.get_hashes_from_range("")
            for h, d in get_existing_hashes(conf.results_dir):
                if h in commit_hashes:
                    commit_hashes.remove(h)
            range_spec = None

        if isinstance(range_spec, list):
            commit_hashes = range_spec
        elif range_spec is not None:
            commit_hashes = repo.get_hashes_from_range(range_spec)

        if len(commit_hashes) == 0:
            log.error("No commit hashes selected")
            return 1

        if steps > 0:
            spacing = max(float(len(commit_hashes)) / steps, 1)
            spaced = []
            i = 0
            while int(i) < len(commit_hashes) and len(spaced) < steps:
                spaced.append(commit_hashes[int(i)])
                i += spacing
            commit_hashes = spaced

        environments = Setup.run(conf=conf, parallel=parallel)
        if len(environments) == 0:
            log.error("No environments selected")
            return 1
        if range_spec != 'master':
            for env in environments:
                if not env.can_install_project():
                    raise util.UserError(
                        "No range spec may be specified if benchmarking in "
                        "an existing environment")

        benchmarks = Benchmarks(conf, regex=bench)
        if len(benchmarks) == 0:
            log.error("No benchmarks selected")
            return 1
        benchmarks.save()

        steps = len(commit_hashes) * len(benchmarks) * len(environments)

        log.info(
            "Running {0} total benchmarks "
            "({1} commits * {2} environments * {3} benchmarks)".format(
                steps, len(commit_hashes),
                len(environments), len(benchmarks)), "green")
        log.set_nitems(steps)

        parallel, multiprocessing = util.get_multiprocessing(parallel)

        _returns['benchmarks'] = benchmarks
        _returns['environments'] = environments
        _returns['machine_params'] = machine_params.__dict__

        for commit_hash in commit_hashes:
            log.info(
                "For {0} commit hash {1}:".format(
                    conf.project, commit_hash[:8]))
            with log.indent():
                for subenv in util.iter_chunks(environments, parallel):
                    log.info("Building for {0}".format(
                        ', '.join([x.name for x in subenv])))
                    with log.indent():
                        args = [(env, conf, commit_hash) for env in subenv]
                        if parallel != 1:
                            pool = multiprocessing.Pool(parallel)
                            successes = pool.map(_do_build_multiprocess, args)
                            pool.close()
                        else:
                            successes = map(_do_build, args)

                    for env, success in zip(subenv, successes):
                        if success:
                            params['python'] = env.python
                            params.update(env.requirements)

                            results = benchmarks.run_benchmarks(
                                env, show_stderr=show_stderr, quick=quick,
                                profile=profile)
                        else:
                            results = benchmarks.skip_benchmarks(env)

                        if dry_run:
                            continue

                        result = Results(
                            params,
                            env.requirements,
                            commit_hash,
                            repo.get_date(commit_hash),
                            env.python)

                        for benchmark_name, d in six.iteritems(results):
                            result.add_time(benchmark_name, d['result'])
                            if 'profile' in d:
                                result.add_profile(
                                    benchmark_name,
                                    d['profile'])

                        result.update_save(conf.results_dir)
