# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
import os
import shutil
import datetime
import pstats
import collections
import socket
import json

import six
import pytest

from os.path import join

from asv import benchmarks
from asv import config
from asv import environment
from asv import runner
from asv import util
from asv.results import Results

from .test_benchmarks import benchmarks_fixture, ASV_CONF_JSON, BENCHMARK_DIR


ON_PYPY = hasattr(sys, 'pypy_version_info')


class ResultsWrapper(object):
    tuple_type = collections.namedtuple('tuple_type', ['result', 'stats', 'samples',
                                                       'params', 'stderr', 'errcode',
                                                       'profile', 'started_at', 'ended_at'])

    def __init__(self, results, benchmarks):
        self.results = results
        self.benchmarks = benchmarks

    def __len__(self):
        return len(list(self.results.get_all_result_keys()))

    def items(self):
        for key in self.results.get_all_result_keys():
            yield key, self[key]

    def __getitem__(self, key):
        params = self.benchmarks[key]['params']
        return self.tuple_type(result=self.results.get_result_value(key, params),
                               stats=self.results.get_result_stats(key, params),
                               samples=self.results.get_result_samples(key, params),
                               stderr=self.results.stderr.get(key),
                               errcode=self.results.errcode.get(key),
                               params=params,
                               profile=(self.results.get_profile(key)
                                        if self.results.has_profile(key) else None),
                               started_at=self.results.started_at[key],
                               ended_at=self.results.ended_at[key])


@pytest.mark.flaky(reruns=1, reruns_delay=5)
def test_run_benchmarks(benchmarks_fixture, tmpdir):
    conf, repo, envs, commit_hash = benchmarks_fixture

    start_timestamp = datetime.datetime.utcnow()

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])

    # Old results to append to
    results = Results.unnamed()
    name = 'time_examples.TimeSuite.time_example_benchmark_1'
    results.add_result(b[name],
                       runner.BenchmarkResult(result=[1],
                                              samples=[[42.0, 24.0]],
                                              number=[1],
                                              errcode=0, stderr='', profile=None),
                       record_samples=True)

    # Run
    runner.run_benchmarks(
        b, envs[0], results=results, profile=True, show_stderr=True,
        append_samples=True, record_samples=True)
    times = ResultsWrapper(results, b)

    end_timestamp = datetime.datetime.utcnow()

    assert len(times) == len(b)
    assert times[
        'time_examples.TimeSuite.time_example_benchmark_1'].result != [None]
    stats = results.get_result_stats(name, b[name]['params'])
    assert isinstance(stats[0]['std'], float)
    # The exact number of samples may vary if the calibration is not fully accurate
    samples = results.get_result_samples(name, b[name]['params'])
    assert len(samples[0]) >= 4
    # Explicitly provided 'prev_samples` should come first
    assert samples[0][:2] == [42.0, 24.0]
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'time_secondary.TimeSecondary.time_exception'].result == [None]
    assert times[
        'subdir.time_subdir.time_foo'].result != [None]
    if not ON_PYPY:
        # XXX: the memory benchmarks don't work on Pypy, since asizeof
        # is CPython-only
        assert times[
            'mem_examples.mem_list'].result[0] > 1000
    assert times[
        'time_secondary.track_value'].result == [42.0]
    assert times['time_secondary.track_value'].profile is not None
    assert isinstance(times['time_examples.time_with_warnings'].stderr, type(''))
    assert times['time_examples.time_with_warnings'].errcode != 0

    assert times['time_examples.TimeWithBadTimer.time_it'].result == [0.0]

    assert times['params_examples.track_param'].params == [["<class 'benchmark.params_examples.ClassOne'>",
                                                               "<class 'benchmark.params_examples.ClassTwo'>"]]
    assert times['params_examples.track_param'].result == [42, 42]

    assert times['params_examples.mem_param'].params == [['10', '20'], ['2', '3']]
    assert len(times['params_examples.mem_param'].result) == 2*2

    assert times['params_examples.ParamSuite.track_value'].params == [["'a'", "'b'", "'c'"]]
    assert times['params_examples.ParamSuite.track_value'].result == [1+0, 2+0, 3+0]

    assert isinstance(times['params_examples.TuningTest.time_it'].result[0], float)
    assert isinstance(times['params_examples.TuningTest.time_it'].result[1], float)

    assert isinstance(times['params_examples.time_skip'].result[0], float)
    assert isinstance(times['params_examples.time_skip'].result[1], float)
    assert util.is_nan(times['params_examples.time_skip'].result[2])

    assert times['peakmem_examples.peakmem_list'].result[0] >= 4 * 2**20

    assert times['cache_examples.ClassLevelSetup.track_example'].result == [500]
    assert times['cache_examples.ClassLevelSetup.track_example2'].result == [500]

    assert times['cache_examples.track_cache_foo'].result == [42]
    assert times['cache_examples.track_cache_bar'].result == [12]
    assert times['cache_examples.track_my_cache_foo'].result == [0]

    assert times['cache_examples.ClassLevelSetupFail.track_fail'].result == [None]
    assert 'raise RuntimeError()' in times['cache_examples.ClassLevelSetupFail.track_fail'].stderr

    assert times['cache_examples.ClassLevelCacheTimeout.track_fail'].result == [None]
    assert times['cache_examples.ClassLevelCacheTimeoutSuccess.track_success'].result == [0]

    assert times['cache_examples.time_fail_second_run'].result == [None]
    assert times['cache_examples.time_fail_second_run'].samples == [None]

    profile_path = join(six.text_type(tmpdir), 'test.profile')
    with open(profile_path, 'wb') as fd:
        fd.write(times['time_secondary.track_value'].profile)
    pstats.Stats(profile_path)

    # Check for running setup on each repeat (one extra run from profile)
    # The output would contain error messages if the asserts in the benchmark fail.
    expected = ["<%d>" % j for j in range(1, 12)]
    assert times['time_examples.TimeWithRepeat.time_it'].stderr.split() == expected

    # Calibration of iterations should not rerun setup
    expected = (['setup']*2, ['setup']*3)
    assert times['time_examples.TimeWithRepeatCalibrate.time_it'].stderr.split() in expected

    # Check tuple-form repeat attribute produced results
    assert 2 <= len(times['time_examples.time_auto_repeat'].samples[0]) <= 4

    # Check run time timestamps
    for name, result in times.items():
        assert result.started_at >= util.datetime_to_js_timestamp(start_timestamp)
        assert result.ended_at >= result.started_at
        assert result.ended_at <= util.datetime_to_js_timestamp(end_timestamp)


def test_quick(benchmarks_fixture):
    # Check that the quick option works
    conf, repo, envs, commit_hash = benchmarks_fixture

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])
    skip_names = [name for name in b.keys() if name != 'time_examples.TimeWithRepeat.time_it']
    b2 = b.filter_out(skip_names)

    results = runner.run_benchmarks(b2, envs[0], quick=True, show_stderr=True)
    times = ResultsWrapper(results, b2)

    assert len(results.get_result_keys(b2)) == 1

    # Check that the benchmark was run only once. The result for quick==False
    # is tested above in test_find_benchmarks
    expected = ["<1>"]
    assert times['time_examples.TimeWithRepeat.time_it'].stderr.split() == expected


def test_skip_param_selection():
    d = {'repo': 'foo'}
    d.update(ASV_CONF_JSON)
    conf = config.Config.from_json(d)

    class DummyEnv(object):
        name = 'env'

    d = [
        {'name': 'test_nonparam', 'params': [], 'version': '1'},
        {'name': 'test_param',
         'params': [['1', '2', '3']],
         'param_names': ['n'],
         'version': '1'}
    ]

    results = Results.unnamed()
    b = benchmarks.Benchmarks(conf, d, [r'test_nonparam', r'test_param\([23]\)'])

    results.add_result(b['test_param'],
                       runner.BenchmarkResult(result=[1, 2, 3], samples=[None]*3, number=[None]*3,
                                              errcode=0, stderr='', profile=None))

    runner.skip_benchmarks(b, DummyEnv(), results)

    assert results._results.get('test_nonparam') == None
    assert results._results['test_param'] == [1, None, None]


@pytest.mark.skipif(not (hasattr(os, 'fork') and hasattr(socket, 'AF_UNIX')),
                    reason="test requires fork and unix sockets")
def test_forkserver(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = 'None'
    conf = config.Config.from_json(d)

    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        f.write("import sys; sys.stdout.write('import-time print')")

    with open(os.path.join('benchmark', 'unimportable.py'), 'w') as f:
        f.write("raise RuntimeError('not importable')")

    env = environment.ExistingEnvironment(conf, sys.executable, {})
    spawner = runner.ForkServer(env, os.path.abspath('benchmark'))

    result_file = os.path.join(tmpdir, 'run-result')

    try:
        out, errcode = spawner.run('time_examples.TimeWithRepeat.time_it', '{}',
                                   None,
                                   result_file,
                                   60,
                                   os.getcwd())
    finally:
        spawner.close()

    assert out.startswith("import-time print<1>")
    assert errcode == 0

    with open(result_file, 'r') as f:
        data = json.load(f)
    assert len(data['samples']) >= 1


needs_unix_socket_mark = pytest.mark.skipif(
    not (hasattr(os, 'fork') and hasattr(socket, 'AF_UNIX')),
    reason="test requires fork and unix sockets")


def clear_pyc(path):
    for fn in os.listdir(path):
        fn = join(path, fn)
        if not os.path.isfile(fn):
            continue
        if fn.lower().endswith('.pyc'):
            os.unlink(fn)

    dn = join(path, '__pycache__')
    if os.path.isdir(dn):
        shutil.rmtree(dn)


@needs_unix_socket_mark
def test_forkserver_preimport(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    os.makedirs('benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = 'None'
    conf = config.Config.from_json(d)

    env = environment.ExistingEnvironment(conf, sys.executable, {})

    #
    # Normal benchmark suite
    #

    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        f.write("print('message')")

    spawner = runner.ForkServer(env, os.path.abspath('benchmark'))
    try:
        success, out = spawner.preimport()
    finally:
        spawner.close()

    assert success == True
    assert out.rstrip() == "message"

    #
    # Benchmark suite that crashes the forkserver
    #

    # NOTE: the .pyc files need to be removed, as Python 2 pyc caching
    # has problems with overwriting files rapidly
    clear_pyc('benchmark')

    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        f.write("import os, sys; print('egassem'); sys.stdout.flush(); os._exit(0)")

    spawner = runner.ForkServer(env, os.path.abspath('benchmark'))
    try:
        success, out = spawner.preimport()
    finally:
        spawner.close()

    assert success == False
    assert out.startswith('asv: benchmark runner crashed')

    #
    # Benchmark suite that has an unimportable file
    #

    clear_pyc('benchmark')

    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        pass

    with open(os.path.join('benchmark', 'bad.py'), 'w') as f:
        f.write("raise RuntimeError()")

    spawner = runner.ForkServer(env, os.path.abspath('benchmark'))
    try:
        success, out = spawner.preimport()
    finally:
        spawner.close()

    assert success == True
    assert out.startswith('Traceback')


@pytest.mark.parametrize('launch_method', [
    'spawn',
    pytest.param('forkserver', marks=needs_unix_socket_mark)
])
def test_run_import_failure(capsys, benchmarks_fixture, launch_method):
    conf, repo, envs, commit_hash = benchmarks_fixture

    with open(os.path.join('benchmark', 'unimportable.py'), 'w') as f:
        f.write('def track_unimportable(): pass')

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])

    skip_names = [name for name in b.keys()
                  if name not in ('time_secondary.track_value', 'unimportable.track_unimportable')]
    b2 = b.filter_out(skip_names)

    #
    # Module with import raising an exception
    #

    with open(os.path.join('benchmark', 'unimportable.py'), 'w') as f:
        f.write('import sys; sys.stderr.write("hello import"); sys.stderr.flush()\n')
        f.write('raise SystemExit(0)')

    results = runner.run_benchmarks(b2, envs[0], show_stderr=False, launch_method=launch_method)
    times = ResultsWrapper(results, b2)

    assert times['time_secondary.track_value'].errcode == 0
    assert times['time_secondary.track_value'].result == [42]

    assert times['unimportable.track_unimportable'].errcode != 0
    err = times['unimportable.track_unimportable'].stderr
    assert 'hello import' in err

    text, err = capsys.readouterr()
    assert 'hello import' not in text

    #
    # Module with import crashing the process
    #

    clear_pyc('benchmark')

    with open(os.path.join('benchmark', 'unimportable.py'), 'w') as f:
        f.write('import sys; sys.stderr.write("hello import"); sys.stderr.flush()\n')
        f.write('import os; os._exit(0)')

    results = runner.run_benchmarks(b2, envs[0], show_stderr=True, launch_method=launch_method)
    times = ResultsWrapper(results, b2)

    assert times['unimportable.track_unimportable'].errcode != 0
    assert times['unimportable.track_unimportable'].stderr

    # track_value may run (spawn) or not (forkserver), so don't check for it

    text, err = capsys.readouterr()

    #
    # Module with import printing output
    #

    clear_pyc('benchmark')

    with open(os.path.join('benchmark', 'unimportable.py'), 'w') as f:
        f.write('import sys; sys.stderr.write("hello import"); sys.stderr.flush()\n')

    results = runner.run_benchmarks(b2, envs[0], show_stderr=True, launch_method=launch_method)
    times = ResultsWrapper(results, b2)

    assert times['time_secondary.track_value'].errcode == 0
    assert times['unimportable.track_unimportable'].errcode != 0

    text, err = capsys.readouterr()
    assert 'hello import' in text
