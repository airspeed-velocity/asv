# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re
import glob
import os
import shutil
import sys
import datetime
import json

import six
import pytest

from os.path import abspath, dirname, join, isfile, relpath

from asv import config, environment, util
from asv.results import iter_results_for_machine
from asv.util import check_output, which

from . import tools
from .tools import dummy_packages


try:
    which('conda')
    HAS_CONDA = True
except (RuntimeError, IOError):
    HAS_CONDA = False


WIN = (os.name == 'nt')


dummy_values = [
    (None, None),
    (1, 1),
    (3, 1),
    (None, 1),
    (6, None),
    (5, 1),
    (6, 1),
    (6, 1),
    (6, 6),
    (6, 6),
]


def generate_basic_conf(tmpdir, repo_subdir=''):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    # Use relative paths on purpose since this is what will be in
    # actual config files

    shutil.copytree(os.path.join(local, 'benchmark'), 'benchmark')

    machine_file = join(tmpdir, 'asv-machine.json')

    shutil.copyfile(join(local, 'asv-machine.json'),
                    machine_file)

    repo_path = tools.generate_test_repo(tmpdir, dummy_values,
                                         subdir=repo_subdir).path

    conf_dict = {
        'env_dir': 'env',
        'benchmark_dir': 'benchmark',
        'results_dir': 'results_workflow',
        'html_dir': 'html',
        'repo': relpath(repo_path),
        'dvcs': 'git',
        'project': 'asv',
        'matrix': {
            "asv_dummy_test_package_1": [""],
            "asv_dummy_test_package_2": tools.DUMMY2_VERSIONS,
        },
    }
    if repo_subdir:
        conf_dict['repo_subdir'] = repo_subdir

    conf = config.Config.from_json(conf_dict)

    if hasattr(sys, 'pypy_version_info'):
        conf.pythons = ["pypy{0[0]}.{0[1]}".format(sys.version_info)]

    return tmpdir, local, conf, machine_file


@pytest.fixture
def basic_conf(tmpdir, dummy_packages):
    return generate_basic_conf(tmpdir)


@pytest.fixture
def basic_conf_with_subdir(tmpdir, dummy_packages):
    return generate_basic_conf(tmpdir, 'some_subdir')


def test_run_publish(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Tests a typical complete run/publish workflow
    tools.run_asv_with_conf(conf, 'run', "master~5..master", '--steps=2',
                            '--quick', '--show-stderr', '--profile',
                            '-a', 'warmup_time=0',
                            _machine_file=machine_file)
    text, err = capfd.readouterr()

    assert len(os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results_workflow'))) == 2
    assert 'asv: benchmark timed out (timeout 0.1s)' in text

    tools.run_asv_with_conf(conf, 'publish')

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))

    # Check parameterized test json data format
    filename = glob.glob(join(tmpdir, 'html', 'graphs', 'arch-x86_64',
                              'asv_dummy_test_package_1',
                              'asv_dummy_test_package_2-' + tools.DUMMY2_VERSIONS[1],
                              'branch-master',
                              'cpu-Blazingly fast', 'machine-orangutan',
                              'os-GNU_Linux', 'python-*', 'ram-128GB',
                              'params_examples.time_skip.json'))[0]
    with open(filename, 'r') as fp:
        data = json.load(fp)
        assert len(data) == 2
        assert isinstance(data[0][0], six.integer_types)  # revision
        assert len(data[0][1]) == 3
        assert len(data[1][1]) == 3
        assert isinstance(data[0][1][0], float)
        assert isinstance(data[0][1][1], float)
        assert data[0][1][2] is None

    # Check that the skip options work
    capfd.readouterr()
    tools.run_asv_with_conf(conf, 'run', "master~5..master", '--steps=2',
                            '--quick', '--skip-existing-successful',
                            '--bench=time_secondary.track_value',
                            '--skip-existing-failed',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    tools.run_asv_with_conf(conf, 'run', "master~5..master", '--steps=2',
                            '--bench=time_secondary.track_value',
                            '--quick', '--skip-existing-commits',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    text, err = capfd.readouterr()
    assert 'Running benchmarks.' not in text

    # Check EXISTING and --environment work
    if HAS_CONDA:
        env_spec = ("-E", "conda:{0[0]}.{0[1]}".format(sys.version_info))
    else:
        env_spec = ("-E", "virtualenv:{0[0]}.{0[1]}".format(sys.version_info))
    tools.run_asv_with_conf(conf, 'run', "EXISTING", '--quick',
                            '--bench=time_secondary.track_value',
                            *env_spec,
                            _machine_file=machine_file)

    # Remove the benchmarks.json file and check publish fails

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    with pytest.raises(util.UserError):
        tools.run_asv_with_conf(conf, 'publish')


def test_continuous(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    if HAS_CONDA:
        env_spec = ("-E", "conda:{0[0]}.{0[1]}".format(sys.version_info))
    else:
        env_spec = ("-E", "virtualenv:{0[0]}.{0[1]}".format(sys.version_info))

    # Check that asv continuous runs
    tools.run_asv_with_conf(conf, 'continuous', "master^", '--show-stderr',
                            '--bench=params_examples.track_find_test',
                            '--bench=params_examples.track_param',
                            '--bench=time_examples.TimeSuite.time_example_benchmark_1',
                            '--attribute=repeat=1', '--attribute=number=1',
                            '--attribute=warmup_time=0',
                            *env_spec, _machine_file=machine_file)

    text, err = capfd.readouterr()
    assert "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY" in text
    assert "+               1                6     6.00  params_examples.track_find_test(2)" in text
    assert "params_examples.ClassOne" in text

    # Check processes were interleaved (timing benchmark was run twice)
    assert re.search(r"For.*commit [a-f0-9]+ (<[a-z0-9~^]+> )?\(round 1/2\)", text, re.M), text

    result_found = False
    for results in iter_results_for_machine(conf.results_dir, "orangutan"):
        result_found = True
        stats = results.get_result_stats('time_examples.TimeSuite.time_example_benchmark_1', [])
        assert stats[0]['repeat'] == 2
    assert result_found


def test_find(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    if WIN and os.path.basename(sys.argv[0]).lower().startswith('py.test'):
        # Multiprocessing in spawn mode can result to problems with py.test
        # Find.run calls Setup.run in parallel mode by default
        pytest.skip("Multiprocessing spawn mode on Windows not safe to run "
                    "from py.test runner.")

    # Test find at least runs
    tools.run_asv_with_conf(conf, 'find', "master~5..master", "params_examples.track_find_test",
                            _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', 'master^'], cwd=conf.repo)

    assert "Greatest regression found: {0}".format(regression_hash[:8]) in output


def test_run_spec(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf
    conf.build_cache_size = 5

    extra_branches = [('master~1', 'some-branch', [12])]
    dvcs_path = os.path.join(tmpdir, 'test_repo2')
    dvcs = tools.generate_test_repo(dvcs_path, [1, 2],
                                    extra_branches=extra_branches)
    conf.repo = dvcs.path

    initial_commit = dvcs.get_hash("master~1")
    master_commit = dvcs.get_hash("master")
    branch_commit = dvcs.get_hash("some-branch")
    template_dir = os.path.join(tmpdir, "results_workflow_template")
    results_dir = os.path.join(tmpdir, 'results_workflow')
    tools.run_asv_with_conf(conf, 'run', initial_commit+"^!",
                            '--bench=time_secondary.track_value',
                            '--quick',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    shutil.copytree(results_dir, template_dir)

    def _test_run(range_spec, branches, expected_commits):
        # Rollback initial results
        shutil.rmtree(results_dir)
        shutil.copytree(template_dir, results_dir)

        args = ["run", "--quick", "--skip-existing-successful",
                "--bench=time_secondary.track_value",
                "-s", "1000"  # large number of steps should be noop
               ]
        if range_spec is not None:
            args.append(range_spec)
        conf.branches = branches
        tools.run_asv_with_conf(conf, *args, _machine_file=machine_file)

        # Check that files for all commits expected were generated
        envs = list(environment.get_environments(conf, None))
        tool_name = envs[0].tool_name

        pyver = conf.pythons[0]
        if pyver.startswith('pypy'):
            pyver = pyver[2:]

        expected = set(['machine.json'])
        for commit in expected_commits:
            for psver in tools.DUMMY2_VERSIONS:
                expected.add('{0}-{1}-py{2}-asv_dummy_test_package_1-asv_dummy_test_package_2{3}.json'.format(
                    commit[:8], tool_name, pyver, psver))

        result_files = os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))

        assert set(result_files) == expected

    for branches, expected_commits in (
        # Without branches in config, shoud just use master
        ([None], [initial_commit, master_commit]),

        # With one branch in config, should just use that branch
        (["some-branch"], [initial_commit, branch_commit]),

        # With two branch in config, should apply to specified branches
        (["master", "some-branch"], [initial_commit, master_commit, branch_commit]),
    ):
        for range_spec in (None, "NEW", "ALL"):
            _test_run(range_spec, branches, expected_commits)


def test_run_build_failure(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    conf.matrix = {}

    # Add a commit that fails to build
    dvcs = tools.Git(conf.repo)
    setup_py = join(dvcs.path, 'setup.py')
    with open(setup_py, 'r') as f:
        setup_py_content = f.read()
    with open(setup_py, 'w') as f:
        f.write("assert False")
    dvcs.add(join(dvcs.path, 'setup.py'))
    dvcs.commit("Break setup.py")
    with open(setup_py, 'w') as f:
        f.write(setup_py_content)
    dvcs.add(join(dvcs.path, 'setup.py'))
    dvcs.commit("Fix setup.py")

    # Test running it
    timestamp = util.datetime_to_js_timestamp(datetime.datetime.utcnow())

    bench_name = 'time_secondary.track_value'
    for commit in ['master^!', 'master~1^!']:
        tools.run_asv_with_conf(conf, 'run', commit,
                                '--quick', '--show-stderr',
                                '--bench', bench_name,
                                _machine_file=machine_file)

    # Check results
    hashes = dvcs.get_branch_hashes()
    fn_broken, = glob.glob(join(tmpdir, 'results_workflow', 'orangutan',
                                    hashes[1][:8] + '-*.json'))
    fn_ok, = glob.glob(join(tmpdir, 'results_workflow', 'orangutan',
                                hashes[0][:8] + '-*.json'))

    data_broken = util.load_json(fn_broken)
    data_ok = util.load_json(fn_ok)

    for data in (data_broken, data_ok):
        assert data['started_at'][bench_name] >= timestamp
        assert data['ended_at'][bench_name] >= data['started_at'][bench_name]

    assert len(data_broken['results']) == 1
    assert len(data_ok['results']) == 1
    assert data_broken['results'][bench_name] is None
    assert data_ok['results'][bench_name] == 42.0

    # Check that parameters were also saved
    assert data_broken['params'] == data_ok['params']


def test_run_with_repo_subdir(basic_conf_with_subdir):
    """
    Check 'asv run' with the Python project inside a subdirectory.
    """
    tmpdir, local, conf, machine_file = basic_conf_with_subdir

    conf.matrix = {}

    # This benchmark imports the project under test (asv_test_repo)
    bench_name = 'params_examples.track_find_test'
    # Test with a single changeset
    tools.run_asv_with_conf(conf, 'run', 'master^!',
                            '--quick', '--show-stderr',
                            '--bench', bench_name,
                            _machine_file=machine_file)

    # Check it ran ok
    fn_results, = glob.glob(join(tmpdir, 'results_workflow', 'orangutan',
                                 '*-*.json'))  # avoid machine.json
    data = util.load_json(fn_results)
    assert data['results'][bench_name] == {'params': [['1', '2']],
                                           'result': [6, 6]}


def test_benchmark_param_selection(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf
    conf.matrix = {}
    tools.generate_test_repo(tmpdir, values=[(1, 2, 3)])
    tools.run_asv_with_conf(conf, 'run', 'master^!',
                            '--quick', '--show-stderr',
                            '--bench', r'track_param_selection\(.*, 3\)',
                            _machine_file=machine_file)

    def get_results():
        results = util.load_json(glob.glob(join(
            tmpdir, 'results_workflow', 'orangutan', '*-*.json'))[0])
        # replacing NaN by 'n/a' make assertions easier
        return ['n/a' if util.is_nan(item) else item
                for item in results['results'][
                    'params_examples.track_param_selection']['result']]

    assert get_results() == [4, 'n/a', 5, 'n/a']
    tools.run_asv_with_conf(conf, 'run', '--show-stderr',
                            '--bench', r'track_param_selection\(1, ',
                            _machine_file=machine_file)
    assert get_results() == [4, 6, 5, 'n/a']
    tools.run_asv_with_conf(conf, 'run', '--show-stderr',
                            '--bench', 'track_param_selection',
                            _machine_file=machine_file)


def test_run_append_samples(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Only one environment
    conf.matrix['asv_dummy_test_package_2'] = conf.matrix['asv_dummy_test_package_2'][:1]

    # Tests multiple calls to "asv run --append-samples"
    def run_it():
        tools.run_asv_with_conf(conf, 'run', "master^!",
                                '--bench', 'time_examples.TimeSuite.time_example_benchmark_1',
                                '--append-samples', '-a', 'repeat=(1, 1, 10.0)', '-a', 'processes=1',
                                '-a', 'number=1', '-a', 'warmup_time=0',
                                _machine_file=machine_file)

    run_it()

    result_dir = join(tmpdir, 'results_workflow', 'orangutan')
    result_fn, = [join(result_dir, fn) for fn in os.listdir(result_dir)
                  if fn != 'machine.json']

    data = util.load_json(result_fn)
    assert data['results']['time_examples.TimeSuite.time_example_benchmark_1']['stats'][0] is not None
    assert len(data['results']['time_examples.TimeSuite.time_example_benchmark_1']['samples'][0]) == 1

    run_it()
    data = util.load_json(result_fn)
    assert len(data['results']['time_examples.TimeSuite.time_example_benchmark_1']['samples'][0]) == 2
