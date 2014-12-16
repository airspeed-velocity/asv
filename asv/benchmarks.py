# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import re
import sys
import tempfile

import six

from .console import log, truncate_left
from .environment import get_environments
from .repo import get_repo
from . import util


# Can't use benchmark.__file__, because that points to the compiled
# file, so it can't be run by another version of Python.
BENCHMARK_RUN_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "benchmark.py")


def run_benchmark(benchmark, root, env, show_stderr=False, quick=False,
                  profile=False):
    """
    Run a single benchmark in another process in the given environment.

    Parameters
    ----------
    benchmark : Benchmark object

    root : str
        Path to benchmark directory in which to find the benchmark

    env : Environment object

    show_stderr : bool
        When `True`, write the stderr out to the console.

    quick : bool, optional
        When `True`, run the benchmark function exactly once.

    profile : bool, optional
        When `True`, run the benchmark through the `cProfile` profiler
        and save the results.

    Returns
    -------
    result : dict
        Returns a dictionary with the following keys:

        - `result`: The numeric value of the benchmark (usually the
          runtime in seconds for a timing benchmark), but may be an
          arbitrary JSON data structure.  Set to `None` if the
          benchmark failed.

        - `profile`: If `profile` is `True`, this key will exist, and
          be a byte string containing the cProfile data.
    """
    name = benchmark['name']
    result = {'result': None}

    log.step()
    name_max_width = util.get_terminal_width() - 33
    short_name = truncate_left(name, name_max_width)
    log.info('Running {0:{1}s}'.format(short_name, name_max_width))

    with log.indent():
        if profile:
            profile_fd, profile_path = tempfile.mkstemp()
            os.close(profile_fd)
        else:
            profile_path = 'None'

        err = ''

        try:
            try:
                output, err = env.run(
                    [BENCHMARK_RUN_SCRIPT, 'run', root, name, str(quick),
                     profile_path],
                    dots=False, timeout=benchmark['timeout'],
                    display_error=False, return_stderr=True,
                    error=False)
            except util.ProcessError:
                log.add(" failed".format(name))
            else:
                try:
                    # The numeric (timing) result is the last line of the
                    # output.  This ensures that if the benchmark
                    # inadvertently writes to stdout we can still read the
                    # numeric output value.
                    parsed = json.loads(output.splitlines()[-1].strip())
                except:
                    log.add(" invalid output".format(name))
                    with log.indent():
                        log.debug(output)
                else:
                    display = util.human_value(parsed, benchmark['unit'])
                    log.add(' {0:>8}'.format(display))
                    result['result'] = parsed

                    if profile:
                        with io.open(profile_path, 'rb') as profile_fd:
                            result['profile'] = profile_fd.read()

            err = err.strip()
            if err:
                if show_stderr:
                    with log.indent():
                        log.error(err)

                result['stderr'] = err

            return result
        finally:
            if profile:
                os.remove(profile_path)


class Benchmarks(dict):
    """
    Manages and runs the set of benchmarks in the project.
    """
    api_version = 1

    def __init__(self, conf, benchmarks=None, regex=None):
        """
        Discover benchmarks in the given `benchmark_dir`.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.
        """
        self._conf = conf
        self._benchmark_dir = conf.benchmark_dir

        if benchmarks is None:
            benchmarks = self.disc_benchmarks(conf)
        else:
            benchmarks = six.itervalues(benchmarks)

        if not regex:
            regex = []
        if isinstance(regex, six.string_types):
            regex = [regex]

        self._all_benchmarks = {}
        for benchmark in benchmarks:
            self._all_benchmarks[benchmark['name']] = benchmark
            for reg in regex:
                if not re.search(reg, benchmark['name']):
                    break
            else:
                self[benchmark['name']] = benchmark

    @classmethod
    def disc_benchmarks(cls, conf):
        """
        Discover all benchmarks in a directory tree.
        """
        root = conf.benchmark_dir

        cls.check_tree(root)

        environments = list(get_environments(conf))
        if len(environments) == 0:
            raise util.UserError("No available environments")

        # Ideally, use an environment in the same Python version as
        # master, but if one isn't found, just default to the first
        # one.
        this_version = "{0:d}.{1:d}".format(
            sys.version_info[0], sys.version_info[1])
        for env in environments:
            if env.python == this_version:
                break
        else:
            env = environments[0]

        log.info("Discovering benchmarks")
        with log.indent():
            repo = get_repo(conf)
            repo.checkout()

            env.install_project(conf)

            output = env.run(
                [BENCHMARK_RUN_SCRIPT, 'discover', root],
                dots=False)

            benchmarks = json.loads(output)
            for benchmark in benchmarks:
                yield benchmark

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

        if not os.path.exists(os.path.join(root, '__init__.py')):
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
        util.write_json(path, self, self.api_version)
        del self['version']

    @classmethod
    def load(cls, conf, regex=None):
        """
        Load the benchmark descriptions from the `benchmarks.json` file.
        If the file is not found, one of the given `environments` will
        be used to discover benchmarks.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.

        Returns
        -------
        benchmarks : Benchmarks object
        """
        def regenerate():
            self = cls(conf, regex=regex)
            self.save()
            return self

        path = cls.get_benchmark_file_path(conf.results_dir)
        if not os.path.exists(path):
            return regenerate()

        d = util.load_json(path)
        version = d['version']
        del d['version']
        if version != cls.api_version:
            # Just re-do the discovery if the file is the wrong
            # version
            return regenerate()

        return cls(conf, benchmarks=d, regex=regex)

    def run_benchmarks(self, env, show_stderr=False, quick=False, profile=False):
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
              be an arbitrary JSON data structure.  Set to `None` if
              the benchmark failed.

            - `profile`: If `profile` is `True`, this key will exist,
              and be a byte string containing the cProfile data.
        """
        log.info("Benchmarking {0}".format(env.name))
        with log.indent():
            times = {}
            benchmarks = sorted(list(six.iteritems(self)))
            for name, benchmark in benchmarks:
                times[name] = run_benchmark(
                    benchmark, self._benchmark_dir, env, show_stderr=show_stderr,
                    quick=quick, profile=profile)
        return times

    def skip_benchmarks(self, env):
        """
        Mark all of the benchmarks as skipped.
        """
        log.warn("Skipping {0}".format(env.name))
        with log.indent():
            times = {}
            for name in self:
                log.step()
                log.warn('Benchmark {0} skipped'.format(name))
                times[name] = {'result': None}
        return times
