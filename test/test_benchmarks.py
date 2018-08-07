# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import shutil
from os.path import join, dirname

import datetime
import pstats
import pytest
import six
import textwrap
from hashlib import sha256

from asv import benchmarks
from asv import runner
from asv import config
from asv import environment
from asv import util
from asv.repo import get_repo

from . import tools

BENCHMARK_DIR = join(dirname(__file__), 'benchmark')

INVALID_BENCHMARK_DIR = join(
    dirname(__file__), 'benchmark.invalid')

ASV_CONF_JSON = {
    'project': 'asv'
    }

if hasattr(sys, 'pypy_version_info'):
    ON_PYPY = True
    ASV_CONF_JSON['pythons'] = ["pypy{0[0]}.{0[1]}".format(sys.version_info)]
else:
    ON_PYPY = False


@pytest.mark.flaky(reruns=1, reruns_delay=5)
def test_find_benchmarks(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    d['branches'] = ["master", "some-missing-branch"]  # missing branches ignored
    conf = config.Config.from_json(d)

    repo = get_repo(conf)

    envs = list(environment.get_environments(conf, None))

    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='secondary')
    assert len(b) == 3

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='example')
    assert len(b) == 26

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                              regex='time_example_benchmark_1')
    assert len(b) == 2

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                              regex=['time_example_benchmark_1',
                                     'some regexp that does not match anything'])
    assert len(b) == 2

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash], regex='custom')
    assert sorted(b.keys()) == ['custom.time_function', 'custom.track_method',
                                'named.track_custom_pretty_name']
    assert 'pretty_name' not in b['custom.track_method']
    assert b['custom.time_function']['pretty_name'] == 'My Custom Function'
    assert b['named.track_custom_pretty_name']['pretty_name'] == 'this.is/the.answer'

    # benchmark param selection with regex
    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='track_param_selection\(.*, 3\)')
    assert list(b.keys()) == ['params_examples.track_param_selection']
    assert b._benchmark_selection['params_examples.track_param_selection'] == [0, 2]
    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='track_param_selection\(1, ')
    assert list(b.keys()) == ['params_examples.track_param_selection']
    assert b._benchmark_selection['params_examples.track_param_selection'] == [0, 1]
    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='track_param_selection')
    assert list(b.keys()) == ['params_examples.track_param_selection']
    assert b._benchmark_selection['params_examples.track_param_selection'] == [0, 1, 2, 3]

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])
    assert len(b) == 36

    assert 'named.OtherSuite.track_some_func' in b

    start_timestamp = datetime.datetime.utcnow()

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])
    times = b.run_benchmarks(envs[0], profile=True, show_stderr=True)

    end_timestamp = datetime.datetime.utcnow()

    assert len(times) == len(b)
    assert times[
        'time_examples.TimeSuite.time_example_benchmark_1']['result'] != [None]
    assert isinstance(times['time_examples.TimeSuite.time_example_benchmark_1']['stats'][0]['std'], float)
    # The exact number of samples may vary if the calibration is not fully accurate
    assert len(times['time_examples.TimeSuite.time_example_benchmark_1']['samples'][0]) >= 4
    # Benchmarks that raise exceptions should have a time of "None"
    assert times[
        'time_secondary.TimeSecondary.time_exception']['result'] == [None]
    assert times[
        'subdir.time_subdir.time_foo']['result'] != [None]
    if not ON_PYPY:
        # XXX: the memory benchmarks don't work on Pypy, since asizeof
        # is CPython-only
        assert times[
            'mem_examples.mem_list']['result'][0] > 1000
    assert times[
        'time_secondary.track_value']['result'] == [42.0]
    assert 'profile' in times[
        'time_secondary.track_value']
    assert 'stderr' in times[
        'time_examples.time_with_warnings']
    assert times['time_examples.time_with_warnings']['errcode'] != 0

    assert times['time_examples.TimeWithBadTimer.time_it']['result'] == [0.0]

    assert times['params_examples.track_param']['params'] == [["<class 'benchmark.params_examples.ClassOne'>",
                                                               "<class 'benchmark.params_examples.ClassTwo'>"]]
    assert times['params_examples.track_param']['result'] == [42, 42]

    assert times['params_examples.mem_param']['params'] == [['10', '20'], ['2', '3']]
    assert len(times['params_examples.mem_param']['result']) == 2*2

    assert times['params_examples.ParamSuite.track_value']['params'] == [["'a'", "'b'", "'c'"]]
    assert times['params_examples.ParamSuite.track_value']['result'] == [1+0, 2+0, 3+0]

    assert isinstance(times['params_examples.TuningTest.time_it']['result'][0], float)
    assert isinstance(times['params_examples.TuningTest.time_it']['result'][1], float)

    assert isinstance(times['params_examples.time_skip']['result'][0], float)
    assert isinstance(times['params_examples.time_skip']['result'][1], float)
    assert util.is_nan(times['params_examples.time_skip']['result'][2])

    assert times['peakmem_examples.peakmem_list']['result'][0] >= 4 * 2**20

    assert times['cache_examples.ClassLevelSetup.track_example']['result'] == [500]
    assert times['cache_examples.ClassLevelSetup.track_example2']['result'] == [500]

    assert times['cache_examples.track_cache_foo']['result'] == [42]
    assert times['cache_examples.track_cache_bar']['result'] == [12]
    assert times['cache_examples.track_my_cache_foo']['result'] == [0]

    assert times['cache_examples.ClassLevelSetupFail.track_fail']['result'] == None
    assert 'raise RuntimeError()' in times['cache_examples.ClassLevelSetupFail.track_fail']['stderr']

    assert times['cache_examples.ClassLevelCacheTimeout.track_fail']['result'] == None
    assert times['cache_examples.ClassLevelCacheTimeoutSuccess.track_success']['result'] == [0]

    profile_path = join(tmpdir, 'test.profile')
    with open(profile_path, 'wb') as fd:
        fd.write(times['time_secondary.track_value']['profile'])
    pstats.Stats(profile_path)

    # Check for running setup on each repeat (one extra run from profile)
    # The output would contain error messages if the asserts in the benchmark fail.
    expected = ["<%d>" % j for j in range(1, 12)]
    assert times['time_examples.TimeWithRepeat.time_it']['stderr'].split() == expected

    # Calibration of iterations should not rerun setup
    expected = (['setup']*2, ['setup']*3)
    assert times['time_examples.TimeWithRepeatCalibrate.time_it']['stderr'].split() in expected

    # Check run time timestamps
    for name, result in times.items():
        assert result['started_at'] >= start_timestamp
        assert result['ended_at'] >= result['started_at']
        assert result['ended_at'] <= end_timestamp


def test_invalid_benchmark_tree(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    d = {}
    d.update(ASV_CONF_JSON)
    d['benchmark_dir'] = INVALID_BENCHMARK_DIR
    d['env_dir'] = "env"
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    repo = get_repo(conf)
    envs = list(environment.get_environments(conf, None))
    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    with pytest.raises(util.UserError):
        b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])


def test_table_formatting():
    benchmark = {'params': [], 'param_names': [], 'unit': 's'}
    result = []
    expected = ["[]"]
    assert runner._format_benchmark_result(result, benchmark) == expected

    benchmark = {'params': [['a', 'b', 'c']], 'param_names': ['param1'], "unit": "seconds"}
    result = list(zip([1e-6, 2e-6, 3e-6], [3e-6, 2e-6, 1e-6]))
    expected = ("======== ==========\n"
                " param1            \n"
                "-------- ----------\n"
                "   a      1.00\u00b13\u03bcs \n"
                "   b      2.00\u00b12\u03bcs \n"
                "   c      3.00\u00b11\u03bcs \n"
                "======== ==========")
    table = "\n".join(runner._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    benchmark = {'params': [["'a'", "'b'", "'c'"], ["[1]", "[2]"]], 'param_names': ['param1', 'param2'], "unit": "seconds"}
    result = list(zip([1, 2, None, 4, 5, float('nan')], [None]*6))
    expected = ("======== ======== =======\n"
                "--            param2     \n"
                "-------- ----------------\n"
                " param1    [1]      [2]  \n"
                "======== ======== =======\n"
                "   a      1.00s    2.00s \n"
                "   b      failed   4.00s \n"
                "   c      5.00s     n/a  \n"
                "======== ======== =======")
    table = "\n".join(runner._format_benchmark_result(result, benchmark, max_width=80))
    assert table == expected

    expected = ("======== ======== ========\n"
                " param1   param2          \n"
                "-------- -------- --------\n"
                "   a       [1]     1.00s  \n"
                "   a       [2]     2.00s  \n"
                "   b       [1]     failed \n"
                "   b       [2]     4.00s  \n"
                "   c       [1]     5.00s  \n"
                "   c       [2]      n/a   \n"
                "======== ======== ========")
    table = "\n".join(runner._format_benchmark_result(result, benchmark, max_width=0))
    assert table == expected


def test_find_benchmarks_cwd_imports(tmpdir):
    # Test that files in the directory above the benchmark suite are
    # not importable

    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    os.makedirs('benchmark')
    with open(os.path.join('benchmark', '__init__.py'), 'w') as f:
        pass

    with open(os.path.join('benchmark', 'test.py'), 'w') as f:
        f.write("""
try:
    import this_should_really_not_be_here
    raise AssertionError('This should not happen!')
except ImportError:
    pass

def track_this():
    return 0
""")

    with open(os.path.join('this_should_really_not_be_here.py'), 'w') as f:
        f.write("raise AssertionError('Should not be imported!')")

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [[0, 1]]).path
    conf = config.Config.from_json(d)

    repo = get_repo(conf)
    envs = list(environment.get_environments(conf, None))
    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex='track_this')
    assert len(b) == 1


def test_quick(tmpdir):
    # Check that the quick option works
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    repo = get_repo(conf)
    envs = list(environment.get_environments(conf, None))
    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash])
    skip_names = [name for name in b.keys() if name != 'time_examples.TimeWithRepeat.time_it']
    times = b.run_benchmarks(envs[0], quick=True, show_stderr=True, skip=skip_names)

    assert len(times) == 1

    # Check that the benchmark was run only once. The result for quick==False
    # is tested above in test_find_benchmarks
    expected = ["<1>"]
    assert times['time_examples.TimeWithRepeat.time_it']['stderr'].split() == expected


def test_code_extraction(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    conf = config.Config.from_json(d)

    repo = get_repo(conf)
    envs = list(environment.get_environments(conf, None))
    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    b = benchmarks.Benchmarks.discover(conf, repo, envs, [commit_hash],
                                       regex=r'^code_extraction\.')

    expected_code = textwrap.dedent("""
    def track_test():
        # module-level 難
        return 0

    def setup():
        # module-level
        pass

    def setup_cache():
        # module-level
        pass
    """).strip()

    bench = b['code_extraction.track_test']
    assert bench['version'] == sha256(bench['code'].encode('utf-8')).hexdigest()
    assert bench['code'] == expected_code

    expected_code = textwrap.dedent("""
    class MyClass:
        def track_test(self):
            # class-level 難
            return 0

    def setup():
        # module-level
        pass

    class MyClass:
        def setup(self):
            # class-level
            pass

        def setup_cache(self):
            # class-level
            pass
    """).strip()

    bench = b['code_extraction.MyClass.track_test']
    assert bench['version'] == sha256(bench['code'].encode('utf-8')).hexdigest()

    if sys.version_info[:2] != (3, 2):
        # Python 3.2 doesn't have __qualname__
        assert bench['code'] == expected_code


def test_asv_benchmark_timings():
    # Check the benchmark runner runs
    util.check_call([sys.executable, '-masv.benchmark', 'timing',
                     '--setup=import time',
                     'time.sleep(0)'])
