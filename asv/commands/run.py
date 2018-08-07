# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

import logging
import traceback
from collections import defaultdict

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..machine import Machine
from ..repo import get_repo
from ..results import (Results, get_existing_hashes,
                       iter_results_for_machine_and_hash)
from .. import environment
from .. import util

from .setup import Setup

from . import common_args


def _do_build(args):
    env, conf, repo, commit_hash = args
    try:
        with log.set_level(logging.WARN):
            env.install_project(conf, repo, commit_hash)
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
    except BaseException as exc:
        raise util.ParallelFailure(str(exc), exc.__class__, traceback.format_exc())


class Run(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "run", help="Run a benchmark suite",
            description="Run a benchmark suite.")

        parser.add_argument(
            'range', nargs='?', default=None,
            help="""Range of commits to benchmark.  For a git
            repository, this is passed as the first argument to ``git
            log``.  See 'specifying ranges' section of the
            `gitrevisions` manpage for more info.  Also accepts the
            special values 'NEW', 'ALL', and 'EXISTING'. 'NEW' will
            benchmark all commits since the latest benchmarked on this
            machine.  'ALL' will benchmark all commits in the project.
            'EXISTING' will benchmark against all commits for which
            there are existing benchmarks on any machine. By default,
            will benchmark the head each configured branches.""")
        parser.add_argument(
            "--steps", "-s", type=common_args.positive_int, default=None,
            help="""Maximum number of steps to benchmark.  This is
            used to subsample the commits determined by range to a
            reasonable number.""")
        common_args.add_bench(parser)
        parser.add_argument(
            "--profile", "-p", action="store_true",
            help="""In addition to timing, run the benchmarks through
            the `cProfile` profiler and store the results.""")
        common_args.add_parallel(parser)
        common_args.add_show_stderr(parser)
        parser.add_argument(
            "--quick", "-q", action="store_true",
            help="""Do a "quick" run, where each benchmark function is
            run only once.  This is useful to find basic errors in the
            benchmark functions faster.  The results are unlikely to
            be useful, and thus are not saved.""")
        common_args.add_environment(parser)
        parser.add_argument(
            "--dry-run", "-n", action="store_true",
            default=None,
            help="""Do not save any results to disk.""")
        common_args.add_machine(parser)
        parser.add_argument(
            "--skip-existing-successful", action="store_true",
            help="""Skip running benchmarks that have previous successful
            results""")
        parser.add_argument(
            "--skip-existing-failed", action="store_true",
            help="""Skip running benchmarks that have previous failed
            results""")
        parser.add_argument(
            "--skip-existing-commits", action="store_true",
            help="""Skip running benchmarks for commits that have existing
            results""")
        parser.add_argument(
            "--skip-existing", "-k", action="store_true",
            help="""Skip running benchmarks that have previous successful
            or failed results""")
        parser.add_argument(
            "--record-samples", action="store_true",
            help="""Store raw measurement samples, not only statistics""")
        parser.add_argument(
            "--no-pull", action="store_true",
            help="Do not pull the repository")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args, **kwargs):
        return cls.run(
            conf=conf, range_spec=args.range, steps=args.steps,
            bench=args.bench, attribute=args.attribute, parallel=args.parallel,
            show_stderr=args.show_stderr, quick=args.quick,
            profile=args.profile, env_spec=args.env_spec,
            dry_run=args.dry_run, machine=args.machine,
            skip_successful=args.skip_existing_successful or args.skip_existing,
            skip_failed=args.skip_existing_failed or args.skip_existing,
            skip_existing_commits=args.skip_existing_commits,
            record_samples=args.record_samples,
            pull=not args.no_pull,
            **kwargs
        )

    @classmethod
    def run(cls, conf, range_spec=None, steps=None, bench=None, attribute=None, parallel=1,
            show_stderr=False, quick=False, profile=False, env_spec=None,
            dry_run=False, machine=None, _machine_file=None, skip_successful=False,
            skip_failed=False, skip_existing_commits=False, record_samples=False,
            pull=True, _returns={}):
        machine_params = Machine.load(
            machine_name=machine,
            _path=_machine_file, interactive=True)
        machine_params.save(conf.results_dir)

        environments = list(environment.get_environments(conf, env_spec))

        if environment.is_existing_only(environments):
            # No repository required, so skip using it
            conf.dvcs = "none"

        repo = get_repo(conf)
        if pull:
            repo.pull()

        if range_spec is None:
            commit_hashes = list(set([repo.get_hash_from_name(branch) for branch in conf.branches]))
        elif range_spec == 'EXISTING':
            commit_hashes = get_existing_hashes(conf.results_dir)
        elif range_spec == "NEW":
            # New commits on each configured branches
            commit_hashes = repo.get_new_branch_commits(
                conf.branches, get_existing_hashes(conf.results_dir))
        elif range_spec == "ALL":
            # All commits on each configured branches
            commit_hashes = repo.get_new_branch_commits(conf.branches, [])
        elif isinstance(range_spec, list):
            commit_hashes = range_spec
        else:
            commit_hashes = repo.get_hashes_from_range(range_spec)

        if len(commit_hashes) == 0:
            log.error("No commit hashes selected")
            return 1

        if steps is not None:
            commit_hashes = util.pick_n(commit_hashes, steps)

        Setup.perform_setup(environments, parallel=parallel)
        if len(environments) == 0:
            log.error("No environments selected")
            return 1

        if range_spec is not None:
            for env in environments:
                if not env.can_install_project():
                    raise util.UserError(
                        "No range spec may be specified if benchmarking in "
                        "an existing environment")

        benchmarks = Benchmarks.discover(conf, repo, environments,
                                         commit_hashes, regex=bench)
        benchmarks.save()
        if len(benchmarks) == 0:
            if bench == ["just-discover"]:
                return 0
            else:
                log.error("No benchmarks selected")
                return 1

        benchmark_count = len(benchmarks)
        steps = len(commit_hashes) * benchmark_count * len(environments)

        log.info(
            "Running {0} total benchmarks "
            "({1} commits * {2} environments * {3} benchmarks)".format(
                steps, len(commit_hashes),
                len(environments), len(benchmarks)))
        log.set_nitems(steps)

        parallel, multiprocessing = util.get_multiprocessing(parallel)

        _returns['benchmarks'] = benchmarks
        _returns['environments'] = environments
        _returns['machine_params'] = machine_params.__dict__

        for commit_hash in commit_hashes:
            skipped_benchmarks = defaultdict(lambda: set())

            if skip_successful or skip_failed or skip_existing_commits:
                try:
                    for result in iter_results_for_machine_and_hash(
                            conf.results_dir, machine_params.machine, commit_hash):

                        if skip_existing_commits:
                            skipped_benchmarks[result.env_name].update(benchmarks)
                            break

                        for key in result.get_result_keys(benchmarks):
                            if key not in benchmarks:
                                continue

                            value = result.get_result_value(key, benchmarks[key]['params'])

                            failed = value is None or (isinstance(value, list) and None in value)

                            if skip_failed and failed:
                                skipped_benchmarks[result.env_name].add(key)
                            if skip_successful and not failed:
                                skipped_benchmarks[result.env_name].add(key)
                except IOError:
                    pass

            for env in environments:
                for bench in benchmarks:
                    if bench in skipped_benchmarks[env.name]:
                        log.step()

            active_environments = [env for env in environments
                                   if set(six.iterkeys(benchmarks))
                                   .difference(skipped_benchmarks[env.name])]

            if not active_environments:
                continue

            if commit_hash:
                log.info(
                    "For {0} commit hash {1}:".format(
                        conf.project, commit_hash[:8]))

            with log.indent():

                for subenv in util.iter_chunks(active_environments, parallel):

                    subenv_name = ', '.join([x.name for x in subenv])

                    log.info("Building for {0}".format(subenv_name))

                    with log.indent():
                        args = [(env, conf, repo, commit_hash) for env in subenv]
                        if parallel != 1:
                            try:
                                pool = multiprocessing.Pool(parallel)
                                try:
                                    successes = pool.map(_do_build_multiprocess, args)
                                    pool.close()
                                    pool.join()
                                finally:
                                    pool.terminate()
                            except util.ParallelFailure as exc:
                                exc.reraise()
                        else:
                            successes = map(_do_build, args)

                    for env, success in zip(subenv, successes):
                        params = dict(machine_params.__dict__)
                        params['python'] = env.python
                        params.update(env.requirements)

                        if success:
                            results = benchmarks.run_benchmarks(
                                env, show_stderr=show_stderr, quick=quick,
                                profile=profile, skip=skipped_benchmarks[env.name],
                                extra_params=attribute)
                        else:
                            results = benchmarks.skip_benchmarks(env)

                        if dry_run or isinstance(env, environment.ExistingEnvironment):
                            continue

                        result = Results(
                            params,
                            env.requirements,
                            commit_hash,
                            repo.get_date(commit_hash),
                            env.python,
                            env.name)

                        for benchmark_name, d in six.iteritems(results):
                            if not record_samples:
                                d['samples'] = None

                            benchmark_version = benchmarks[benchmark_name]['version']
                            result.add_result(benchmark_name, d, benchmark_version)

                        result.update_save(conf.results_dir)
