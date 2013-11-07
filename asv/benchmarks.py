# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import unittest
import os
import subprocess

from .console import console
from . import util

# TODO: Make this discovery based on names, not unittest instances


class Benchmarks(object):
    def __init__(self, benchmark_dir):
        self.benchmark_dir = benchmark_dir

        self.benchmarks = unittest.defaultTestLoader.discover(
            self.benchmark_dir)

        flat = []

        def recurse(item):
            if isinstance(item, unittest.TestSuite):
                for benchmark in item:
                    recurse(benchmark)
            elif isinstance(item, unittest.TestCase):
                flat.append(item.id())

        recurse(self.benchmarks)
        self.flat = flat

    def __len__(self):
        return len(self.flat)

    def run_benchmarks(self, env):
        run_script = os.path.join(
            os.path.dirname(__file__), "do_benchmark.py")

        times = {}
        for test_id in self.flat:
            console.step(test_id + ": ")
            try:
                output = env.run([run_script, self.benchmark_dir, test_id])
            except subprocess.CalledProcessError:
                console.add("failed", "red")
            else:
                console.add(util.human_time(output))
                times[test_id] = float(output)

        return times
