# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, join, isfile, isdir
import shutil

import six
import pytest

from asv import config
from asv import util
from asv.repo import get_repo


from . import tools

RESULT_DIR = abspath(join(dirname(__file__), 'example_results'))
BENCHMARK_DIR = abspath(join(dirname(__file__), 'benchmark'))


def test_publish(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    result_dir = join(tmpdir, 'sample_results')
    os.makedirs(result_dir)
    os.makedirs(join(result_dir, 'cheetah'))

    # Synthesize history with two branches that both have commits
    result_files = [fn for fn in os.listdir(join(RESULT_DIR, 'cheetah'))
                    if fn.endswith('.json') and fn != 'machine.json']
    result_files.sort()
    master_values = list(range(len(result_files)*2//3))
    branch_values = list(range(len(master_values), len(result_files)))
    dvcs = tools.generate_test_repo(tmpdir, master_values, 'git',
                                    [('master~6', 'some-branch', branch_values)])

    # Copy and modify result files, fixing commit hashes and setting result
    # dates to distinguish the two branches
    master_commits = dvcs.get_branch_hashes('master')
    only_branch = [x for x in dvcs.get_branch_hashes('some-branch')
                   if x not in master_commits]
    commits = master_commits + only_branch
    for k, item in enumerate(zip(result_files, commits)):
        fn, commit = item
        src = join(RESULT_DIR, 'cheetah', fn)
        dst = join(result_dir, 'cheetah', commit[:8] + fn[8:])
        data = util.load_json(src, cleanup=False)
        data['commit_hash'] = commit
        if commit in only_branch:
            data['date'] = -k
        else:
            data['date'] = k
        util.write_json(dst, data)

    shutil.copyfile(join(RESULT_DIR, 'benchmarks.json'),
                    join(result_dir, 'benchmarks.json'))
    shutil.copyfile(join(RESULT_DIR, 'cheetah', 'machine.json'),
                    join(result_dir, 'cheetah', 'machine.json'))

    # Publish the synthesized data
    conf = config.Config.from_json(
        {'benchmark_dir': BENCHMARK_DIR,
         'results_dir': result_dir,
         'html_dir': join(tmpdir, 'html'),
         'repo': dvcs.path,
         'project': 'asv'})

    tools.run_asv_with_conf(conf, 'publish')

    # Check output
    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))
    assert not isdir(join(tmpdir, 'html', 'graphs', 'Cython', 'arch-x86_64',
                          'branch-some-branch'))
    assert not isdir(join(tmpdir, 'html', 'graphs', 'Cython-null', 'arch-x86_64',
                          'branch-some-branch'))
    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['branch'] == ['master']

    def check_file(branch, cython):
        fn = join(tmpdir, 'html', 'graphs', cython, 'arch-x86_64', 'branch-' + branch,
                  'cpu-Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)',
                  'machine-cheetah', 'numpy-1.8', 'os-Linux (Fedora 20)', 'python-2.7', 'ram-8.2G',
                  'time_coordinates.time_latitude.json')
        data = util.load_json(fn, cleanup=False)
        if branch == 'master':
            # we set all dates positive for master above
            assert all(x[0] >= 0 for x in data)
        else:
            # we set some dates negative for some-branch above
            assert any(x[0] < 0 for x in data) and any(x[0] >= 0 for x in data)

    check_file("master", "Cython")
    check_file("master", "Cython-null")

    # Publish with branches set in the config
    conf.branches = ['master', 'some-branch']
    tools.run_asv_with_conf(conf, 'publish')

    # Check output
    check_file("master", "Cython")
    check_file("master", "Cython-null")
    check_file("some-branch", "Cython")
    check_file("some-branch", "Cython-null")

    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['branch'] == ['master', 'some-branch']
    assert index['params']['Cython'] == ['', None]
    assert index['params']['ram'] == ['8.2G', 8804682956.8]


@pytest.fixture(params=["git"])
def generate_result_dir(request, tmpdir):
    tmpdir = six.text_type(tmpdir)
    dvcs_type = request.param

    def _generate_result_dir(values, commits_without_result=None):
        dvcs = tools.generate_repo_from_ops(
            tmpdir, dvcs_type, [("commit", i) for i in range(len(values))])
        commits = list(reversed(dvcs.get_branch_hashes()))
        commit_values = {}
        commits_without_result = [commits[i] for i in commits_without_result or []]
        for commit, value in zip(commits, values):
            if commit not in commits_without_result:
                commit_values[commit] = value
        conf = tools.generate_result_dir(tmpdir, dvcs, commit_values)
        repo = get_repo(conf)
        return conf, repo, commits
    return _generate_result_dir

GRAPH_PATH = join("graphs", "branch-master", "machine-tarzan", "time_func.json")


def test_regression_simple(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", GRAPH_PATH, {}, None, [
        [[None, repo.get_date_from_name(commits[5])]], 10.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_range(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 6 * [10], commits_without_result=[5])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", GRAPH_PATH, {}, None, [
        [[repo.get_date_from_name(commits[4]), repo.get_date_from_name(commits[6])]], 10.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_fixed(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10] + [1])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": []}
    assert regressions == expected


def test_regression_double(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10] + 5 * [15])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", GRAPH_PATH, {}, None, [
        [[None, repo.get_date_from_name(commits[5])], [None, repo.get_date_from_name(commits[10])]], 15.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_first_commits(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 10 * [10])
    # Ignore before 5th commit
    conf.regressions_first_commits = {"^time_*": commits[5]}
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    assert regressions == {"regressions": []}

    # Ignore all
    conf.regressions_first_commits = {"^time_*": None}
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    assert regressions == {"regressions": []}

    # Ignore before 2th commit (-> regression not ignored)
    conf.regressions_first_commits = {"^time_*": commits[2]}
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", GRAPH_PATH, {}, None, [
        [[None, repo.get_date_from_name(commits[5])]], 10.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_parameterized(generate_result_dir):
    before = {"params": [["a", "b", "c", "d"]], "result": [5, 1, 1, 10]}
    after = {"params": [["a", "b", "c", "d"]], "result": [6, 1, 10, 1]}
    conf, repo, commits = generate_result_dir(5 * [before] + 5 * [after])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {'regressions': [[
        'time_func(a)',
        GRAPH_PATH,
        {},
        0,
        [[[None, repo.get_date_from_name(commits[5])]], 6.0, 5.0],
    ], [
        'time_func(c)',
        GRAPH_PATH,
        {},
        2,
        [[[None, repo.get_date_from_name(commits[5])]], 10.0, 1.0],
    ]]}
    assert regressions == expected


def test_regression_multiple_branches(tmpdir):
    tmpdir = six.text_type(tmpdir)
    dvcs_type = "git"
    master = "master"
    dvcs = tools.generate_repo_from_ops(
        tmpdir, dvcs_type, [
            ("commit", 1),
            ("checkout", "stable", master),
            ("commit", 1),
            ("checkout", master),
        ] + 4 * [
            ("commit", 1),
            ("checkout", "stable"),
            ("commit", 1),
            ("checkout", master),
        ] + 5 * [
            ("commit", 1),
            ("checkout", "stable"),
            ("commit", 2),
            ("checkout", master),
        ],
    )
    commit_values = {}
    branches = dict(
        (branch, list(reversed(dvcs.get_branch_hashes(branch))))
        for branch in (master, "stable")
    )
    for branch, values in (
        (master, 10 * [1]),
        ("stable", 5 * [1] + 5 * [2]),
    ):
        for commit, value in zip(branches[branch], values):
            commit_values[commit] = value
    conf = tools.generate_result_dir(tmpdir, dvcs, commit_values)
    conf.branches = [master, "stable"]
    tools.run_asv_with_conf(conf, "publish")
    repo = get_repo(conf)
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    graph_path = join('graphs', 'branch-stable', 'machine-tarzan', 'time_func.json')
    # Regression occur on 5th commit of stable branch
    date = repo.get_date_from_name(branches["stable"][5])
    expected = {'regressions': [['time_func', graph_path, {'branch': 'stable'}, None,
                                 [[[None, date]], 2.0, 1.0]]]}
    assert regressions == expected
