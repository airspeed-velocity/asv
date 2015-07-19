# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import glob
import os
from os.path import abspath, dirname, join, isfile, relpath
import shutil
import sys

import six
import json
import pytest

from asv import config
from asv.commands.run import Run
from asv.commands.publish import Publish
from asv.commands.find import Find
from asv.commands.continuous import Continuous
from asv.util import check_output, which

from . import tools


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
            "six": [None],
            "colorama": ["0.3.1", "0.3.3"]
        }
    })

    return tmpdir, local, conf, machine_file


def test_run_publish(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Tests a typical complete run/publish workflow
    Run.run(conf, range_spec="master~5..master", steps=2,
            _machine_file=machine_file, quick=True, show_stderr=True)
    text, err = capfd.readouterr()

    assert len(os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results_workflow'))) == 2
    assert 'asv: benchmark timed out (timeout 0.1s)' in text

    Publish.run(conf)

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))

    # Check parameterized test json data format
    filename = glob.glob(join(tmpdir, 'html', 'graphs', 'arch-x86_64', 'branch-master',
                              'colorama-0.3.3',  'cpu-Blazingly fast', 'machine-orangutan',
                              'os-GNU', 'Linux', 'python-*', 'ram-128GB',
                              'six', 'params_examples.time_skip.json'))[0]
    with open(filename, 'r') as fp:
        data = json.load(fp)
        assert len(data) == 2
        assert isinstance(data[0][0], six.integer_types)  # date
        assert len(data[0][1]) == 3
        assert len(data[1][1]) == 3
        assert isinstance(data[0][1][0], float)
        assert isinstance(data[0][1][1], float)
        assert data[0][1][2] is None

    # Check that the skip options work
    capfd.readouterr()
    Run.run(conf, range_spec="master~5..master", steps=2,
            _machine_file=join(tmpdir, 'asv-machine.json'), quick=True,
            skip_successful=True, skip_failed=True)
    Run.run(conf, range_spec="master~5..master", steps=2,
            _machine_file=join(tmpdir, 'asv-machine.json'), quick=True,
            skip_existing_commits=True)
    text, err = capfd.readouterr()
    assert 'Running benchmarks.' not in text

    # Check EXISTING works
    Run.run(conf, range_spec="EXISTING",
            _machine_file=machine_file, quick=True)

    # Remove the benchmarks.json file to make sure publish can
    # regenerate it

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    Publish.run(conf)


def test_continuous(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Check that asv continuous runs
    Continuous.run(conf, branch="master^", _machine_file=machine_file, show_stderr=True)

    text, err = capfd.readouterr()
    assert "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY" in text
    assert "params_examples.track_find_test(2)              1.0        6.0   6.00000000x" in text
    assert "params_examples.ClassOne" in text


def test_find(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    if WIN and os.path.basename(sys.argv[0]).lower().startswith('py.test'):
        # Multiprocessing in spawn mode can result to problems with py.test
        # Find.run calls Setup.run in parallel mode by default
        pytest.skip("Multiprocessing spawn mode on Windows not safe to run "
                    "from py.test runner.")

    # Test find at least runs
    Find.run(conf, "master~5..master", "params_examples.track_find_test",
             _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', 'master^'], cwd=conf.repo)

    assert "Greatest regression found: {0}".format(regression_hash[:8]) in output


def _test_run_branches(tmpdir, dvcs, conf, machine_file, range_spec,
                       branches, initial_commit):
    # Find the current head commits for each branch
    commits = [initial_commit]
    for branch in branches:
        commits.append(dvcs.get_hash(branch))

    # Run tests
    Run.run(conf, range_spec=range_spec,
            _machine_file=machine_file, quick=True)

    # Check that files for all commits expected were generated
    expected = set(['machine.json'])
    for commit in commits:
        for psver in ['0.3.1', '0.3.3']:
            expected.add('{0}-py{1[0]}.{1[1]}-colorama{2}-six.json'.format(
                commit[:8], sys.version_info, psver))

    result_files = os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))

    if range_spec == 'NEW':
        assert set(result_files) == expected
    elif range_spec == 'ALL':
        assert set(expected).difference(result_files) == set([])
    else:
        raise ValueError()


def test_run_new_all(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf
    conf.wheel_cache_size = 5

    extra_branches = [('master~1', 'some-branch', [12])]
    dvcs_path = os.path.join(tmpdir, 'test_repo2')
    dvcs = tools.generate_test_repo(dvcs_path, [1, 2],
                                    extra_branches=extra_branches)
    conf.repo = dvcs.path

    initial_commit = dvcs.get_hash("master~1")

    def init_results():
        results_dir = os.path.join(tmpdir, 'results_workflow')
        if os.path.isdir(results_dir):
            shutil.rmtree(results_dir)
        Run.run(conf, range_spec=initial_commit+"^!",
                bench=["time_secondary.track_value"],
                _machine_file=join(tmpdir, 'asv-machine.json'), quick=True,
                skip_successful=True, skip_failed=True)

    # Without branches in config, should just use master
    init_results()
    _test_run_branches(tmpdir, dvcs, conf, machine_file, 'NEW',
                       branches=['master'], initial_commit=initial_commit)

    init_results()
    _test_run_branches(tmpdir, dvcs, conf, machine_file, 'ALL',
                       branches=['master'], initial_commit=initial_commit)

    # With branches in config
    conf.branches = ['master', 'some-branch']

    init_results()
    _test_run_branches(tmpdir, dvcs, conf, machine_file, 'NEW',
                       branches=['master', 'some-branch'], initial_commit=initial_commit)

    init_results()
    _test_run_branches(tmpdir, dvcs, conf, machine_file, 'ALL',
                       branches=['master', 'some-branch'], initial_commit=initial_commit)
