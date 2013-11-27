# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

import six

from asv import benchmarks
from asv import environment

# The benchmark dir is named '.benchmark' so that py.test doesn't look
# in there for unit tests.
BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), '.benchmark')


def test_find_benchmarks():
    b = benchmarks.Benchmarks(BENCHMARK_DIR)
    assert len(b) == 4


def test_find_benchmarks_regex():
    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'secondary')
    assert len(b) == 2

    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'example')
    assert len(b) == 2

    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'test_example_benchmark_1')
    assert len(b) == 1


def test_run_benchmarks(tmpdir):
    envdir = six.text_type(tmpdir.join("env"))
    version = "{0[0]}.{0[1]}".format(sys.version_info)
    env = environment.Environment(envdir, version, {})
    env.setup()

    b = benchmarks.Benchmarks(BENCHMARK_DIR)
    times = b.run_benchmarks(env)

    assert len(times) == 4
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'test_secondary_benchmarks.TestSecondary.test_exception'] is None
