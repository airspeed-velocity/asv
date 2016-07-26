# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import os
from os.path import abspath, dirname, join, isfile, isdir
import shutil

import six
import pytest
import xml.etree.ElementTree as etree
try:
    import hglib
except ImportError:
    hglib = None


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
        try:
            data = util.load_json(src, cleanup=False)
        except util.UserError:
            # intentionally malformed file, ship it as is
            shutil.copyfile(src, dst)
            continue
        data['commit_hash'] = commit
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

    repo = get_repo(conf)
    revision_to_hash = dict((r, h) for h, r in six.iteritems(repo.get_revisions(commits)))

    def check_file(branch, cython):
        fn = join(tmpdir, 'html', 'graphs', cython, 'arch-x86_64', 'branch-' + branch,
                  'cpu-Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)',
                  'machine-cheetah', 'numpy-1.8', 'os-Linux (Fedora 20)', 'python-2.7', 'ram-8.2G',
                  'time_coordinates.time_latitude.json')
        data = util.load_json(fn, cleanup=False)
        data_commits = [revision_to_hash[x[0]] for x in data]
        if branch == "master":
            assert all(c in master_commits for c in data_commits)
        else:
            # Must contains commits from some-branch
            assert any(c in only_branch for c in data_commits)
            # And commits from master
            assert any(c in master_commits for c in data_commits)

        # Check that revisions are strictly increasing
        assert all(x[0] < y[0] for x, y in zip(data, data[1:]))

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

    expected_graph_list = [{'Cython': cython, 'arch': 'x86_64',
                            'branch': branch,
                            'cpu': 'Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)',
                            'machine': 'cheetah',
                            'numpy': '1.8',
                            'os': 'Linux (Fedora 20)',
                            'python': '2.7',
                            'ram': '8.2G'}
                            for cython in ["", None] for branch in ["master", "some-branch"]]
    d = dict(expected_graph_list[0])
    d['ram'] = 8804682956.8
    expected_graph_list.append(d)

    assert len(index['graph_param_list']) == len(expected_graph_list)
    for item in expected_graph_list:
        assert item in index['graph_param_list']


@pytest.fixture(params=[
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
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

def _graph_path(dvcs_type):
    if dvcs_type == "git":
        master = "master"
    elif dvcs_type == "hg":
        master = "default"
    return join("graphs", "branch-{0}".format(master), "machine-tarzan", "time_func.json")

def test_regression_simple(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[None, 5, 1.0, 10.0]], 10.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_range(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 6 * [10], commits_without_result=[5])
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[4, 6, 1.0, 10.0]], 10.0, 1.0,
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
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[None, 5, 1.0, 10.0], [None, 10, 10.0, 15.0]], 15.0, 1.0,
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
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[None, 5, 1.0, 10.0]], 10.0, 1.0,
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
        _graph_path(repo.dvcs),
        {},
        0,
        [[[None, 5, 5.0, 6.0]], 6.0, 5.0],
    ], [
        'time_func(c)',
        _graph_path(repo.dvcs),
        {},
        2,
        [[[None, 5, 1.0, 10.0]], 10.0, 1.0],
    ]]}
    assert regressions == expected


@pytest.mark.parametrize("dvcs_type", [
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
def test_regression_multiple_branches(dvcs_type, tmpdir):
    tmpdir = six.text_type(tmpdir)
    if dvcs_type == "git":
        master = "master"
    elif dvcs_type == "hg":
        master = "default"
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
    revision = repo.get_revisions(commit_values.keys())[branches["stable"][5]]
    expected = {'regressions': [['time_func', graph_path, {'branch': 'stable'}, None,
                                 [[[None, revision, 1.0, 2.0]], 2.0, 1.0]]]}
    assert regressions == expected


@pytest.mark.parametrize("dvcs_type", [
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
def test_regression_non_monotonic(dvcs_type, tmpdir):
    tmpdir = six.text_type(tmpdir)
    now = datetime.datetime.now()

    dates = [now + datetime.timedelta(days=i) for i in range(5)] + [now - datetime.timedelta(days=i) for i in range(5)]
    # last commit in the past
    dates[-1] = now - datetime.timedelta(days=1)

    dvcs = tools.generate_repo_from_ops(tmpdir, dvcs_type, [("commit", i, d) for i, d in enumerate(dates)])
    commits = list(reversed(dvcs.get_branch_hashes()))
    commit_values = {}
    for commit, value in zip(commits, 5 * [1] + 5 * [2]):
        commit_values[commit] = value
    conf = tools.generate_result_dir(tmpdir, dvcs, commit_values)
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {'regressions': [['time_func', _graph_path(dvcs_type), {}, None,
                                 [[[None, 5, 1.0, 2.0]], 2.0, 1.0]]]}
    assert regressions == expected


def test_regression_threshold(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1.0] + 5 * [1.1] + 5 * [2.0])

    conf.regressions_thresholds = {'.*': 0}
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[None, 5, 1.0, 1.1], [None, 10, 1.1, 2.0]], 2.0, 1.0,
    ]]]}
    assert regressions == expected

    conf.regressions_thresholds = {'.*': 0, 'time_func.*': 0.2}
    tools.run_asv_with_conf(conf, "publish")
    regressions = util.load_json(join(conf.html_dir, "regressions.json"))
    expected = {"regressions": [["time_func", _graph_path(repo.dvcs), {}, None, [
        [[None, 10, 1.1, 2.0]], 2.0, 1.0,
    ]]]}
    assert regressions == expected


def test_regression_atom_feed(generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10] + 5 * [15])
    tools.run_asv_with_conf(conf, "publish")

    commits = list(reversed(repo.get_branch_commits(None)))

    tree = etree.parse(join(conf.html_dir, "regressions.xml"))
    root = tree.getroot()

    assert root.tag == '{http://www.w3.org/2005/Atom}feed'
    entries = root.findall('{http://www.w3.org/2005/Atom}entry')

    # Check entry titles
    assert len(entries) == 2
    title = entries[0].find('{http://www.w3.org/2005/Atom}title')
    assert title.text == '900.00% time_func'
    title = entries[1].find('{http://www.w3.org/2005/Atom}title')
    assert title.text == '50.00% time_func'

    # Check there's a link of some sort to the website in the content
    content = entries[0].find('{http://www.w3.org/2005/Atom}content')
    assert ('<a href="index.html#time_func?commits=' + commits[5]) in content.text
    content = entries[1].find('{http://www.w3.org/2005/Atom}content')
    assert ('<a href="index.html#time_func?commits=' + commits[10]) in content.text

    # Smoke check ids
    id_1 = entries[0].find('{http://www.w3.org/2005/Atom}id')
    id_2 = entries[1].find('{http://www.w3.org/2005/Atom}id')
    assert id_1.text != id_2.text


@pytest.mark.parametrize("dvcs_type", [
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
def test_regression_atom_feed_update(dvcs_type, tmpdir):
    # Check that adding new commits which only change values preserves
    # feed entry ids
    tmpdir = six.text_type(tmpdir)
    values = 5 * [1] + 5 * [10] + 5*[15.70, 15.31]
    dvcs = tools.generate_repo_from_ops(
        tmpdir, dvcs_type, [("commit", i) for i in range(len(values))])
    commits = list(reversed(dvcs.get_branch_hashes()))

    # Old results (drop last 6)
    commit_values = {}
    for commit, value in zip(commits, values[:-5]):
        commit_values[commit] = value
    conf = tools.generate_result_dir(tmpdir, dvcs, commit_values)

    tools.run_asv_with_conf(conf, "publish")

    old_tree = etree.parse(join(conf.html_dir, "regressions.xml"))

    # New results (values change, regressing revisions stay same)
    for commit, value in zip(commits, values):
        commit_values[commit] = value

    shutil.rmtree(conf.results_dir)
    shutil.rmtree(conf.html_dir)
    conf = tools.generate_result_dir(tmpdir, dvcs, commit_values)

    tools.run_asv_with_conf(conf, "publish")

    new_tree = etree.parse(join(conf.html_dir, "regressions.xml"))

    # Check ids didn't change
    old_root = old_tree.getroot()
    new_root = new_tree.getroot()

    old_entries = old_root.findall('{http://www.w3.org/2005/Atom}entry')
    new_entries = new_root.findall('{http://www.w3.org/2005/Atom}entry')

    assert len(new_entries) == len(old_entries) == 2

    for j, (a, b) in enumerate(zip(new_entries, old_entries)):
        a_id = a.find('{http://www.w3.org/2005/Atom}id')
        b_id = b.find('{http://www.w3.org/2005/Atom}id')
        assert a_id.text == b_id.text

        a_content = a.find('{http://www.w3.org/2005/Atom}content')
        b_content = b.find('{http://www.w3.org/2005/Atom}content')
        assert a_content.text != b_content.text
