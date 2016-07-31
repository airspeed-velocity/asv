# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import glob
import os
from os.path import abspath, dirname, join, isfile, relpath
import shutil
import sys
import datetime

import six
import json
import pytest

from asv import config, environment, util
from asv.util import check_output, which

from . import tools


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


@pytest.fixture
def basic_conf(tmpdir):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    # Use relative paths on purpose since this is what will be in
    # actual config files

    shutil.copytree(os.path.join(local, 'benchmark'), 'benchmark')

    machine_file = join(tmpdir, 'asv-machine.json')

    shutil.copyfile(join(local, 'asv-machine.json'),
                    machine_file)

    repo_path = tools.generate_test_repo(tmpdir, dummy_values).path

    conf = config.Config.from_json({
        'env_dir': 'env',
        'benchmark_dir': 'benchmark',
        'results_dir': 'results_workflow',
        'html_dir': 'html',
        'repo': relpath(repo_path),
        'dvcs': 'git',
        'project': 'asv',
        'matrix': {
            "six": [""],
            "colorama": ["0.3.6", "0.3.7"]
        }
    })

    if hasattr(sys, 'pypy_version_info'):
        conf.pythons = ["pypy{0[0]}.{0[1]}".format(sys.version_info)]

    return tmpdir, local, conf, machine_file


def test_run_publish(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Tests a typical complete run/publish workflow
    tools.run_asv_with_conf(conf, 'run', "master~5..master", '--steps=2',
                            '--quick', '--show-stderr',
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
    filename = glob.glob(join(tmpdir, 'html', 'graphs', 'arch-x86_64', 'branch-master',
                              'colorama-0.3.7',  'cpu-Blazingly fast', 'machine-orangutan',
                              'os-GNU', 'Linux', 'python-*', 'ram-128GB',
                              'six', 'params_examples.time_skip.json'))[0]
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
                            '--skip-existing-failed',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    tools.run_asv_with_conf(conf, 'run', "master~5..master", '--steps=2',
                            '--quick', '--skip-existing-commits',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    text, err = capfd.readouterr()
    assert 'Running benchmarks.' not in text

    # Check EXISTING and --environment work
    if HAS_CONDA:
        env_spec = ("-E", "conda:{0[0]}.{0[1]}".format(sys.version_info))
    else:
        env_spec = ("-E", "virtualenv:{0[0]}.{0[1]}".format(sys.version_info))
    tools.run_asv_with_conf(conf, 'run', "EXISTING", '--quick', *env_spec,
                            _machine_file=machine_file)

    # Remove the benchmarks.json file to make sure publish can
    # regenerate it

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    tools.run_asv_with_conf(conf, 'publish')


def test_continuous(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    if HAS_CONDA:
        env_spec = ("-E", "conda:{0[0]}.{0[1]}".format(sys.version_info))
    else:
        env_spec = ("-E", "virtualenv:{0[0]}.{0[1]}".format(sys.version_info))

    # Check that asv continuous runs
    tools.run_asv_with_conf(conf, 'continuous', "master^", '--show-stderr',
                            *env_spec, _machine_file=machine_file)

    text, err = capfd.readouterr()
    assert "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY" in text
    assert "+     1.00s      6.00s      6.00  params_examples.track_find_test(2)" in text
    assert "params_examples.ClassOne" in text


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
    conf.wheel_cache_size = 5

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
            for psver in ['0.3.6', '0.3.7']:
                expected.add('{0}-{1}-py{2}-colorama{3}-six.json'.format(
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
