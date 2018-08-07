# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import contextlib
import io
import os
import pstats
import sys
import tempfile

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..environment import get_environments, is_existing_only
from ..machine import Machine
from ..profiling import ProfilerGui
from ..repo import get_repo
from ..results import iter_results_for_machine
from ..util import hash_equal, iter_subclasses
from .. import util

from . import common_args


@contextlib.contextmanager
def temp_profile(profile_data):
    profile_fd, profile_path = tempfile.mkstemp()
    try:
        with io.open(profile_fd, 'wb', closefd=True) as fd:
            fd.write(profile_data)

        yield profile_path
    finally:
        os.remove(profile_path)


class Profile(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "profile",
            help="""Run the profiler on a particular benchmark on a
            particular revision""",
            description="Profile a benchmark")

        parser.add_argument(
            'benchmark',
            help="""The benchmark to profile.  Must be a
            fully-specified benchmark name. For parameterized benchmark, it
            must include the parameter combination to use, e.g.:
            benchmark_name(param0, param1, ...)""")
        parser.add_argument(
            'revision', nargs='?',
            help="""The revision of the project to profile.  May be a
            commit hash, or a tag or branch name.""")
        parser.add_argument(
            '--gui', '-g',
            help="""Display the profile in the given gui.  Use
            --gui=list to list available guis.""")
        parser.add_argument(
            '--output', '-o',
            help="""Save the profiling information to the given file.
            This file is in the format written by the `cProfile`
            standard library module.  If not provided, prints a simple
            text-based profiling report to the console.""")
        parser.add_argument(
            '--force', '-f', action='store_true',
            help="""Forcibly re-run the profile, even if the data
            already exists in the results database.""")
        common_args.add_environment(parser)

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def find_guis(cls):
        cls.guis = {}
        for x in iter_subclasses(ProfilerGui):
            if x.name is not None and x.is_available():
                cls.guis[x.name] = x

    @classmethod
    def run_from_conf_args(cls, conf, args, **kwargs):
        return cls.run(
            conf=conf, benchmark=args.benchmark, revision=args.revision,
            gui=args.gui, output=args.output, force=args.force,
            env_spec=args.env_spec, **kwargs)

    @classmethod
    def run(cls, conf, benchmark, revision=None, gui=None, output=None,
            force=False, env_spec=None,
            _machine_file=None):
        cls.find_guis()

        if gui == 'list':
            log.info("Available profiler GUIs:")
            with log.indent():
                for x in cls.guis.values():
                    log.info("{0}: {1}".format(x.name, x.description))
            return

        if gui is not None and gui not in cls.guis:
            raise util.UserError(
                "Unknown profiler GUI {0}".format(gui))

        if benchmark is None:
            raise util.UserError(
                "Must specify benchmark to run")

        environments = list(get_environments(conf, env_spec))

        if is_existing_only(environments):
            # No repository required, so skip using it
            conf.dvcs = "none"

        repo = get_repo(conf)
        repo.pull()

        machine_name = Machine.get_unique_machine_name()
        if revision is None:
            revision = conf.branches[0]
        commit_hash = repo.get_hash_from_name(revision)

        profile_data = None
        checked_out = set()

        # First, we see if we already have the profile in the results
        # database
        if not force and commit_hash:
            for result in iter_results_for_machine(
                    conf.results_dir, machine_name):
                if hash_equal(commit_hash, result.commit_hash):
                    if result.has_profile(benchmark):
                        env_matched = any(result.env.name == env.name
                                          for env in environments)
                        if env_matched:
                            if result.env.name not in checked_out:
                                # We need to checkout the correct commit so that
                                # the line numbers in the profile data match up with
                                # what's in the source tree.
                                result.env.checkout_project(repo, commit_hash)
                                checked_out.add(result.env.name)
                            profile_data = result.get_profile(benchmark)
                            break

        if profile_data is None:
            if len(environments) == 0:
                log.error("No environments selected")
                return

            if revision is not None:
                for env in environments:
                    if not env.can_install_project():
                        raise util.UserError(
                            "An explicit revision may not be specified when "
                            "using an existing environment.")

            env = environments[0]

            if env.python != "{0}.{1}".format(*sys.version_info[:2]):
                raise util.UserError(
                    "Profiles must be run in the same version of Python as the "
                    "asv master process")

            benchmarks = Benchmarks.discover(conf, repo, environments,
                                             [commit_hash],
                                             regex='^{0}$'.format(benchmark))
            if len(benchmarks) != 1:
                raise util.UserError(
                    "Could not find benchmark {0}".format(benchmark))

            if not force:
                log.info(
                    "Profile data does not already exist. "
                    "Running profiler now.")
            else:
                log.info("Running profiler")
            with log.indent():
                env.install_project(conf, repo, commit_hash)

                results = benchmarks.run_benchmarks(
                    env, show_stderr=True, quick=False, profile=True)

                profile_data = results[benchmark]['profile']

        if gui is not None:
            log.debug("Opening gui {0}".format(gui))
            with temp_profile(profile_data) as profile_path:
                return cls.guis[gui].open_profiler_gui(profile_path)
        elif output is not None:
            with io.open(output, 'wb') as fd:
                fd.write(profile_data)
        else:
            with temp_profile(profile_data) as profile_path:
                stats = pstats.Stats(profile_path)
                stats.sort_stats('cumulative')
                stats.print_stats()
