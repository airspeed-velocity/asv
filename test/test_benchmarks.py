# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

import pytest
import six

from asv import benchmarks
from asv import environment

# The benchmark dir is named '.benchmark' so that py.test doesn't look
# in there for unit tests.
BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), '.benchmark')

INVALID_BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), '.benchmark.invalid')


def test_find_benchmarks():
    b = benchmarks.Benchmarks(BENCHMARK_DIR)
    assert len(b) == 7


def test_find_benchmarks_regex():
    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'secondary')
    assert len(b) == 3

    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'example')
    assert len(b) == 3

    b = benchmarks.Benchmarks(BENCHMARK_DIR, 'time_example_benchmark_1')
    assert len(b) == 1


def test_run_benchmarks(tmpdir):
    envdir = six.text_type(tmpdir.join("env"))
    version = "{0[0]}.{0[1]}".format(sys.version_info)
    env = environment.Environment(envdir, version, {})
    env.setup()

    b = benchmarks.Benchmarks(BENCHMARK_DIR)
    times = b.run_benchmarks(env)

    assert len(times) == 7
    assert times[
        'time_examples.TimeSuite.time_example_benchmark_1'] is not None
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'time_secondary.TimeSecondary.time_exception'] is None
    assert times[
        'subdir.time_subdir.time_foo'] is not None
    assert times[
        'mem_examples.mem_list'] == sys.getsizeof([0] * 255)
    assert times[
        'time_secondary.track_value'] == 42.0


def test_invalid_benchmark_tree():
    with pytest.raises(ValueError):
        b = benchmarks.Benchmarks(INVALID_BENCHMARK_DIR)
