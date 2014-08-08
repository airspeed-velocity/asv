# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import pstats
import pytest
import six

from asv import benchmarks
from asv import config
from asv import environment

BENCHMARK_DIR = os.path.join(os.path.dirname(__file__), 'benchmark')

INVALID_BENCHMARK_DIR = os.path.join(
    os.path.dirname(__file__), 'benchmark.invalid')

ASV_CONF_JSON = {
    'benchmark_dir': BENCHMARK_DIR,
    'repo': 'https://github.com/spacetelescope/asv.git',
    'project': 'asv'
    }


def test_find_benchmarks(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = os.path.join(tmpdir, "env")
    conf = config.Config.from_json(d)

    b = benchmarks.Benchmarks(conf, regex='secondary')
    assert len(b) == 3

    b = benchmarks.Benchmarks(conf, regex='example')
    assert len(b) == 5

    b = benchmarks.Benchmarks(conf, regex='time_example_benchmark_1')
    assert len(b) == 2

    b = benchmarks.Benchmarks(conf)
    assert len(b) == 9

    envs = list(environment.get_environments(conf))
    b = benchmarks.Benchmarks(conf)
    times = b.run_benchmarks(envs[0], profile=True, show_exc=True)

    assert len(times) == 9
    assert times[
        'time_examples.TimeSuite.time_example_benchmark_1']['result'] is not None
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'time_secondary.TimeSecondary.time_exception']['result'] is None
    assert times[
        'subdir.time_subdir.time_foo']['result'] is not None
    assert times[
        'mem_examples.mem_list']['result'] > 2000
    assert times[
        'time_secondary.track_value']['result'] == 42.0
    assert 'profile' in times[
        'time_secondary.track_value']

    profile_path = os.path.join(tmpdir, 'test.profile')
    with open(profile_path, 'wb') as fd:
        fd.write(times['time_secondary.track_value']['profile'])
    pstats.Stats(profile_path)


def test_invalid_benchmark_tree(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    d = {}
    d.update(ASV_CONF_JSON)
    d['benchmark_dir'] = INVALID_BENCHMARK_DIR
    d['env_dir'] = os.path.join(tmpdir, "env")
    conf = config.Config.from_json(d)

    with pytest.raises(ValueError):
        b = benchmarks.Benchmarks(conf)
