# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import os
import re
import tempfile
import itertools
import datetime

import six

from .console import log
from . import util
from . import runner
from .repo import NoSuchNameError


class Benchmarks(dict):
    """
    Manages and runs the set of benchmarks in the project.
    """
    api_version = 2

    def __init__(self, conf, benchmarks, regex=None):
        """
        Initialize a list of benchmarks.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        benchmarks : list
            Benchmarks as from Benchmarks._disc_benchmarks
            or loaded from a file.

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.
            For parameterized benchmarks, the regex match against
            `funcname(param0, param1, ...)` to include the parameter
            combination in regex filtering.
        """
        self._conf = conf
        self._benchmark_dir = conf.benchmark_dir

        if not regex:
            regex = []
        if isinstance(regex, six.string_types):
            regex = [regex]

        self._all_benchmarks = {}
        self._benchmark_selection = {}
        for benchmark in benchmarks:
            self._all_benchmarks[benchmark['name']] = benchmark
            if benchmark['params']:
                self._benchmark_selection[benchmark['name']] = []
                for idx, param_set in enumerate(
                        itertools.product(*benchmark['params'])):
                    name = '%s(%s)' % (
                        benchmark['name'],
                        ', '.join(param_set))
                    if not regex or any(re.search(reg, name) for reg in regex):
                        self[benchmark['name']] = benchmark
                        self._benchmark_selection[benchmark['name']].append(idx)
            else:
                self._benchmark_selection[benchmark['name']] = None
                if not regex or any(re.search(reg, benchmark['name']) for reg in regex):
                    self[benchmark['name']] = benchmark

    @classmethod
    def discover(cls, conf, repo, environments, commit_hash, regex=None):
        """
        Discover benchmarks in the given `benchmark_dir`.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        repo : Repo object
            The project's repository

        environments : list of Environment
            List of environments available for benchmark discovery.

        commit_hash : list of str
            Commit hashes to use for benchmark discovery.

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.

        """
        benchmarks = cls._disc_benchmarks(conf, repo, environments, commit_hash)
        return cls(conf, benchmarks, regex=regex)

    @classmethod
    def _disc_benchmarks(cls, conf, repo, environments, commit_hashes):
        """
        Discover all benchmarks in a directory tree.
        """
        root = conf.benchmark_dir

        cls.check_tree(root)

        if len(environments) == 0:
            raise util.UserError("No available environments")

        # Append default commit hashes, to make it probably the
        # discovery usually succeeds
        commit_hashes = list(commit_hashes)
        for branch in conf.branches:
            try:
                branch_hash = repo.get_hash_from_name(branch)
            except NoSuchNameError:
                continue

            if branch_hash not in commit_hashes:
                commit_hashes.append(branch_hash)

        log.info("Discovering benchmarks")
        with log.indent():
            last_err = None
            for env, commit_hash in itertools.product(environments, commit_hashes):
                env.create()

                if last_err is not None:
                    log.warn("Build failed: trying different commit")

                try:
                    env.install_project(conf, repo, commit_hash)
                    break
                except util.ProcessError as err:
                    # Installation failed
                    last_err = err
            else:
                log.error(str(last_err))
                raise util.UserError("Failed to build the project.")

            result_dir = tempfile.mkdtemp()
            try:
                result_file = os.path.join(result_dir, 'result.json')
                env.run(
                    [runner.BENCHMARK_RUN_SCRIPT, 'discover',
                     os.path.abspath(root),
                     os.path.abspath(result_file)],
                    cwd=result_dir,
                    dots=False)

                with open(result_file, 'r') as fp:
                    benchmarks = json.load(fp)
            finally:
                util.long_path_rmtree(result_dir)

        return benchmarks

    @classmethod
    def check_tree(cls, root):
        """
        Check the benchmark tree for files with the same name as
        directories.

        Also, ensure that every directory has an __init__.py file.

        Raises
        ------
        ValueError :
            A .py file and directory with the same name (excluding the
            extension) were found.
        """
        if os.path.basename(root) == '__pycache__':
            return

        if not os.path.isfile(os.path.join(root, '__init__.py')):
            raise util.UserError(
                "No __init__.py file in '{0}'".format(root))

        # First, check for the case where a .py file and a directory
        # have the same name (without the extension).  This can't be
        # handled, so just raise an exception
        found = set()
        for filename in os.listdir(root):
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                filename, ext = os.path.splitext(filename)
                if ext == '.py':
                    found.add(filename)

        for dirname in os.listdir(root):
            path = os.path.join(root, dirname)
            if os.path.isdir(path):
                if dirname in found:
                    raise util.UserError(
                        "Found a directory and python file with same name in "
                        "benchmark tree: '{0}'".format(path))
                cls.check_tree(path)

    @classmethod
    def get_benchmark_file_path(cls, results_dir):
        """
        Get the path to the benchmarks.json file in the results dir.
        """
        return os.path.join(results_dir, "benchmarks.json")

    def save(self):
        """
        Save the ``benchmarks.json`` file, which is a cached set of the
        metadata about the discovered benchmarks, in the results dir.
        """
        path = self.get_benchmark_file_path(self._conf.results_dir)
        util.write_json(path, self._all_benchmarks, self.api_version)

    @classmethod
    def load(cls, conf):
        """
        Load the benchmark descriptions from the `benchmarks.json` file.
        If the file is not found, one of the given `environments` will
        be used to discover benchmarks.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        Returns
        -------
        benchmarks : Benchmarks object
        """
        try:
            path = cls.get_benchmark_file_path(conf.results_dir)
            if not os.path.isfile(path):
                raise util.UserError("Benchmark list file {} missing!".format(path))
            d = util.load_json(path, cleanup=False, api_version=cls.api_version)
            benchmarks = six.itervalues(d)
            return cls(conf, benchmarks)
        except util.UserError as err:
            if "asv update" in str(err):
                # Don't give conflicting instructions
                raise
            raise util.UserError("{}\nUse `asv run --bench just-discover` to "
                                 "regenerate benchmarks.json".format(str(err)))

    def run_benchmarks(self, env, show_stderr=False, quick=False, profile=False,
                       skip=None, extra_params=None):
        """
        Run all of the benchmarks in the given `Environment`.

        Parameters
        ----------
        env : Environment object
            Environment in which to run the benchmarks.

        show_stderr : bool, optional
            When `True`, display any stderr emitted by the benchmark.

        quick : bool, optional
            When `True`, run each benchmark function exactly once.
            This is useful to quickly find errors in the benchmark
            functions, without taking the time necessary to get
            accurate timings.

        profile : bool, optional
            When `True`, run the benchmark through the `cProfile`
            profiler.

        skip : set, optional
            Benchmark names to skip.

        extra_params : dict, optional
            Override values for benchmark attributes.

        Returns
        -------
        dict : result
            Returns a dictionary where the keys are benchmark names
            and the values are dictionaries containing information
            about running that benchmark.

            Each of the values in the dictionary has the following
            keys:

            - `result`: The numeric value of the benchmark (usually
              the runtime in seconds for a timing benchmark), but may
              be an arbitrary JSON data structure. For parameterized tests,
              this is a dictionary with keys 'params' and 'result', where
              the value of 'params' contains a list of lists of parameter values,
              and 'result' is a list of results, corresponding to itertools.product
              iteration over parameters.
              Set to `None` if the benchmark failed.

            - `profile`: If `profile` is `True`, this key will exist,
              and be a byte string containing the cProfile data.
        """
        log.info("Benchmarking {0}".format(env.name))

        benchmarks = sorted(list(six.iteritems(self)))

        # Remove skipped benchmarks
        if skip:
            benchmarks = [
                (name, benchmark) for (name, benchmark) in
                benchmarks if name not in skip]

        # Setup runner and run benchmarks
        times = {}
        benchmark_runner = runner.BenchmarkRunner(benchmarks,
                                                  self._benchmark_dir,
                                                  show_stderr=show_stderr,
                                                  quick=quick,
                                                  extra_params=extra_params,
                                                  profile=profile,
                                                  selected_idx=self._benchmark_selection)
        jobs = benchmark_runner.plan()
        times = benchmark_runner.run(jobs, env)

        return times

    def skip_benchmarks(self, env):
        """
        Mark benchmarks as skipped.
        """
        log.warn("Skipping {0}".format(env.name))
        with log.indent():
            times = {}
            for name in self:
                log.step()
                log.warn('Benchmark {0} skipped'.format(name))
                timestamp = datetime.datetime.utcnow()
                times[name] = {'result': None,
                               'samples': None,
                               'stats': None,
                               'params': [],
                               'started_at': timestamp,
                               'ended_at': timestamp}
        return times
