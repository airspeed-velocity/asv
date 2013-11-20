# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import inspect
import re
import textwrap
import unittest
import os

from .console import console
from . import util


class Benchmarks(object):
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

        benchmarks = unittest.defaultTestLoader.discover(
            self._benchmark_dir)

        flat = {}

        def recurse(item):
            if isinstance(item, unittest.TestSuite):
                for benchmark in item:
                    recurse(benchmark)
            elif isinstance(item, unittest.TestCase):
                for regex in bench:
                    if not re.search(regex, item.id()):
                        break
                else:
                    code = inspect.getsource(getattr(item, item._testMethodName))
                    code = textwrap.dedent(code)
                    flat[item.id()] = code

        recurse(benchmarks)
        self._benchmarks = flat.keys()
        self._code = flat

    def __len__(self):
        return len(self._benchmarks)

    def run_benchmarks(self, env):
        """
        Run all of the benchmarks in the given `Environment`.
        """
        run_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "do_benchmark.py")

        times = {}
        for benchmark_id in self._benchmarks:
            console.step(benchmark_id + ": ")
            try:
                output = env.run(
                    [run_script, self._benchmark_dir, benchmark_id],
                    # TODO: Get timeout from benchmark
                    dots=False, timeout=60)
            except util.ProcessError:
                console.add("failed", "red")
                times[benchmark_id] = None
            else:
                console.add(util.human_time(output))
                times[benchmark_id] = float(output)

        return times

    def skip_benchmarks(self):
        """
        Mark all of the benchmarks as skipped.
        """
        times = {}
        for benchmark_id in self._benchmarks:
            console.step(benchmark_id + ": ")
            console.add("skipped", "yellow")
            times[benchmark_id] = None

        return times

    def get_code(self, benchmark):
        return self._code[benchmark]
