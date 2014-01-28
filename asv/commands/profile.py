# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import contextlib
import io
import os
import pstats
import tempfile

import six

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..environment import get_environments
from ..machine import Machine
from ..profile import ProfilerGui
from ..repo import get_repo
from ..results import iter_results_for_machine
from ..util import hash_equal, iter_subclasses


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
    guis = dict(
        (x.name, x) for x in iter_subclasses(ProfilerGui) if x.name is not None)

    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "profile",
            help="""Run the profiler on a particular benchmark on a
            particular revision""",
            description="Profile a benchmark")

        parser.add_argument(
            'benchmark', nargs=1,
            help="""The benchmark to profile.  Must be a
            fully-specified benchmark name.""")
        parser.add_argument(
            'revision', nargs=1,
            help="""The revision of the project to profile.  May be a
            commit hash, or a tag or brach name.""")
        parser.add_argument(
            '--gui', '-g', nargs='?',
            help="""Display the profile in the given gui.  Currently
            supported guis are: {0}""".format(', '.join(cls.guis.keys())))
        parser.add_argument(
            '--output', '-o', nargs='?',
            help="""Save the profiling information to the given file.
            This file is in the format written by the `cProfile`
            standard library module.  If not provided, prints a simple
            text-based profiling report to the console.""")
        parser.add_argument(
            '--force', '-f', action='store_true',
            help="""Forcibly re-run the profile, even if the data
            already exists in the results database.""")
        parser.add_argument(
            '--environment', '-e', nargs='?',
            help="""Which environment to use.  Your benchmarking
            project may have multiple environments if it has a
            dependency matrix or multiple versions of Python
            specified.  This should the name of an environment
            directory as already created by the run command. If `None`
            is specified, one will be chosen at random.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, conf, args):
        return cls.run(
            conf=conf, benchmark=args.benchmark[0], revision=args.revision[0],
            gui=args.gui, output=args.output, force=args.force,
            environment=args.environment)

    @classmethod
    def run(cls, conf, benchmark, revision, gui=None, output=None,
            force=False, environment=None, _machine_file=None):

        if gui is not None and gui not in cls.guis:
            raise ValueError("Unknown profiler GUI {0}".format(gui))

        machine_name = Machine.get_unique_machine_name()
        repo = get_repo(conf.repo, conf.project)
        commit_hash = repo.get_hash_from_tag(revision)

        profile_data = None

        # Even if we don't end up running the profile, we need to
        # checkout the correct commit_hash so the line numbers in the
        # profile data match up with what's in the source tree.
        repo.checkout(commit_hash)

        # First, we see if we already have the profile in the results
        # database
        if not force:
            for result in iter_results_for_machine(
                    conf.results_dir, machine_name):
                if hash_equal(commit_hash, result.commit_hash):
                    if result.has_profile(benchmark):
                        if (environment is None or
                            result.env.name == environment):
                            profile_data = result.get_profile(benchmark)
                            break

        if profile_data is None:
            environments = list(
                get_environments(
                    conf.env_dir, conf.pythons, conf.matrix))

            if len(environments) == 0:
                log.error("No environments selected")
                return

            if environment is None:
                env = environments[0]
            else:
                for env in environments:
                    if env.name == environment:
                        break
                else:
                    raise ValueError(
                        "Environment {0} not found.".format(environment))

            benchmarks = Benchmarks(conf, regex=benchmark)
            if len(benchmarks) != 1:
                raise ValueError(
                    "Could not find benchmark {0}".format(benchmark))

            if not force:
                log.info(
                    "Profile data does not already exist. "
                    "Running profiler now.")
            else:
                log.info("Running profiler")
            with log.indent():
                env.install_project(
                    conf.project, os.path.abspath(conf.project))

                results = benchmarks.run_benchmarks(
                    env, show_exc=True, quick=False, profile=True)

                profile_data = results[benchmark]['profile']

        if gui is not None:
            with temp_profile(profile_data) as profile_path:
                cls.guis[gui].open_profiler_gui(profile_path)
        elif output is not None:
            with io.open(output, 'wb') as fd:
                fd.write(profile_data)
        else:
            with temp_profile(profile_data) as profile_path:
                stats = pstats.Stats(profile_path)
                stats.sort_stats('cumtime')
                stats.print_stats()
