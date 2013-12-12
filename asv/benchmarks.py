# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import imp
import inspect
import os
import re

import six

from . import benchmark as bm
from .console import console
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
    console.enable()
    console.step(benchmark.name + ": ")
    try:
        output = env.run(
            [BENCHMARK_RUN_SCRIPT, root, benchmark.name],
            dots=False, timeout=benchmark.timeout,
            display_error=True)
    except util.ProcessError:
        console.add("failed", "red")
        return None
    else:
        try:
            # The numeric (timing) result is the last line of the
            # output.  This ensures that if the benchmark
            # inadvertently writes to stdout we can still read the
            # numeric output value.
            output = float(output.splitlines()[-1])
        except:
            console.add("invalid output", "red")
            return None
        if benchmark.unit == 'seconds':
            console.add(util.human_time(output))
        else:
            console.add(str(output))
        return output


class Benchmarks(dict):
    """
    Manages and runs the set of benchmarks in the project.
    """
    def __init__(self, benchmark_dir, bench=None):
        """
        Discover benchmarks in the given `benchmark_dir`.

        `bench` is a list of regular expressions for the benchmarks to
        run.  If none are provided, all benchmarks are run.
        """
        self._benchmark_dir = benchmark_dir
        if not bench:
            bench = []
        if isinstance(bench, six.string_types):
            bench = [bench]

        for benchmark in self.disc_benchmarks(self._benchmark_dir):
            for regex in bench:
                if not re.search(regex, benchmark.name):
                    break
            else:
                self[benchmark.name] = benchmark

    @classmethod
    def disc_class(cls, klass):
        """
        Iterate over all benchmarks in a given class.

        For each method with a special name, yields a Benchmark
        object.
        """
        for key, val in six.iteritems(klass.__dict__):
            bm_type = bm.get_benchmark_type_from_name(key)

            if bm_type is not None and inspect.isfunction(val):
                yield bm_type.from_class_method(klass, key)

    @classmethod
    def disc_objects(cls, module):
        """
        Iterate over all benchmarks in a given module, returning
        Benchmark objects.

        For each class definition, looks for any methods with a
        special name.

        For each free function, yields all functions with a special
        name.
        """
        for key, val in six.iteritems(module.__dict__):
            if inspect.isclass(val):
                for benchmark in cls.disc_class(val):
                    yield benchmark
            elif inspect.isfunction(val):
                bm_type = bm.get_benchmark_type_from_name(key)
                if bm_type is not None:
                    yield bm_type.from_function(val)

    @classmethod
    def disc_files(cls, root, package=''):
        """
        Iterate over all .py files in a given directory tree.
        """
        for filename in os.listdir(root):
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                filename, ext = os.path.splitext(filename)
                if ext == '.py':
                    module = imp.load_source(package + filename, path)
                    yield module
            elif os.path.isdir(path):
                for x in cls.disc_files(path, package + filename + "."):
                    yield x

    @classmethod
    def disc_benchmarks(cls, root):
        """
        Discover all benchmarks in a given directory tree.
        """
        cls.check_files(root)

        for module in cls.disc_files(root):
            for benchmark in cls.disc_objects(module):
                yield benchmark

    @classmethod
    def check_files(cls, root):
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
                cls.check_files(path)

    def run_benchmarks(self, env, show_exc=False):
        """
        Run all of the benchmarks in the given `Environment`.
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
