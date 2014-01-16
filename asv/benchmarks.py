# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import os
import re
import sys

import six

from .console import console
from .environment import get_environments
from .repo import get_repo
from . import util


# Can't use benchmark.__file__, because that points to the compiled
# file, so it can't be run by another version of Python.
BENCHMARK_RUN_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "benchmark.py")


def run_benchmark(benchmark, root, env, show_exc=False):
    """
    Run a single benchmark in another process in the given environment.

    Parameters
    ----------
    benchmark : Benchmark object

    root : str
        Path to benchmark directory in which to find the benchmark

    env : Environment object

    show_exc : bool
        When `True`, write the exception to the console if the
        benchmark fails.

    Returns
    -------
    result : float or None
        If `float` the numeric value of the benchmark (usually the
        runtime in seconds for a timing benchmark) or None if the
        benchmark failed.
    """
    console.step(benchmark['name'] + ": ")
    try:
        output = env.run(
            [BENCHMARK_RUN_SCRIPT, 'run', root, benchmark['name']],
            dots=False, timeout=benchmark['timeout'],
            display_error=show_exc)
    except util.ProcessError:
        console.add("failed", "red")
        return None
    else:
        try:
            # The numeric (timing) result is the last line of the
            # output.  This ensures that if the benchmark
            # inadvertently writes to stdout we can still read the
            # numeric output value.
            output = json.loads(output.splitlines()[-1])
        except:
            console.add("invalid output", "red")
            return None

        if isinstance(output, (int, float)):
            if benchmark['unit'] == 'seconds':
                display = util.human_time(output)
            elif benchmark['unit'] == 'bytes':
                display = util.human_file_size(output)
            else:
                display = json.dumps(output)
        else:
            display = json.dumps(output)
        console.add(display)

        return output


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

        environments = list(get_environments(
            conf.env_dir, conf.pythons, conf.matrix))
        if len(environments) == 0:
            raise ValueError("No available environments")

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

        repo = get_repo(conf.repo, conf.project)
        repo.checkout()
        repo.clean()

        env.install_requirements()
        env.uninstall(conf.project)
        env.install(os.path.abspath(conf.project), editable=True)

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

        Raises
        ------
        ValueError :
            A .py file and directory with the same name (excluding the
            extension) were found.
        """
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
                    raise ValueError(
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

    def run_benchmarks(self, env, show_exc=False):
        """
        Run all of the benchmarks in the given `Environment`.

        Parameters
        ----------
        env : Environment object
            Environment in which to run the benchmarks.

        show_exc : bool, optional
            When `True`, display the exception traceback when running
            a benchmark fails.
        """
        times = {}
        for name, benchmark in six.iteritems(self):
            times[name] = run_benchmark(
                benchmark, self._benchmark_dir, env, show_exc=show_exc)
        return times

    def skip_benchmarks(self):
        """
        Mark all of the benchmarks as skipped.
        """
        times = {}
        for name in self:
            console.step(name + ": ")
            console.add("skipped", "yellow")
            times[name] = None
        return times
