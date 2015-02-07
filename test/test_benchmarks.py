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
from asv import util

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
    assert len(b) == 12

    b = benchmarks.Benchmarks(conf, regex='time_example_benchmark_1')
    assert len(b) == 2

    b = benchmarks.Benchmarks(conf)
    assert len(b) == 16

    envs = list(environment.get_environments(conf))
    b = benchmarks.Benchmarks(conf)
    times = b.run_benchmarks(envs[0], profile=True, show_stderr=True)

    assert len(times) == 16
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
    assert 'stderr' in times[
        'time_examples.time_with_warnings']
    assert times['time_examples.time_with_warnings']['errcode'] != 0

    assert times['params_examples.track_param']['result']['params'] == [["<class 'benchmark.params_examples.ClassOne'>",
                                                                         "<class 'benchmark.params_examples.ClassTwo'>"]]
    assert times['params_examples.track_param']['result']['result'] == [42, 42]

    assert times['params_examples.mem_param']['result']['params'] == [['10', '20'], ['2', '3']]
    assert len(times['params_examples.mem_param']['result']['result']) == 2*2

    assert times['params_examples.ParamSuite.track_value']['result']['params'] == [["'a'", "'b'", "'c'"]]
    assert times['params_examples.ParamSuite.track_value']['result']['result'] == [1+0, 2+0, 3+0]

    assert isinstance(times['params_examples.TuningTest.time_it']['result']['result'][0], float)

    assert isinstance(times['params_examples.time_skip']['result']['result'][0], float)
    assert isinstance(times['params_examples.time_skip']['result']['result'][1], float)
    assert times['params_examples.time_skip']['result']['result'][2] is None

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

    with pytest.raises(util.UserError):
        b = benchmarks.Benchmarks(conf)


def test_table_formatting():
    benchmark = {'params': [], 'param_names': [], 'unit': 's'}
    result = []
    expected = ["[]"]
    assert benchmarks._format_benchmark_result(result, benchmark) == expected

    benchmark = {'params': [['a', 'b', 'c']], 'param_names': ['param1'], "unit": "seconds"}
    result = [1e-6, 2e-6, 3e-6]
    expected = ("======== ========\n"
                " param1          \n"
                "-------- --------\n"
                "   a      1.00\u03bcs \n"
                "   b      2.00\u03bcs \n"
                "   c      3.00\u03bcs \n"
                "======== ========")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    benchmark = {'params': [["'a'", "'b'", "'c'"], ["[1]", "[2]"]], 'param_names': ['param1', 'param2'], "unit": "seconds"}
    result = [1, 2, 3, 4, 5, 6]
    expected = ("======== ======= =======\n"
                "--            param2    \n"
                "-------- ---------------\n"
                " param1    [1]     [2]  \n"
                "======== ======= =======\n"
                "   a      1.00s   2.00s \n"
                "   b      3.00s   4.00s \n"
                "   c      5.00s   6.00s \n"
                "======== ======= =======")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    expected = ("======== ======== =======\n"
                " param1   param2         \n"
                "-------- -------- -------\n"
                "   a       [1]     1.00s \n"
                "   a       [2]     2.00s \n"
                "   b       [1]     3.00s \n"
                "   b       [2]     4.00s \n"
                "   c       [1]     5.00s \n"
                "   c       [2]     6.00s \n"
                "======== ======== =======")
    table = "\n".join(benchmarks._format_benchmark_result(result, benchmark, max_width=0))
    assert table == expected
