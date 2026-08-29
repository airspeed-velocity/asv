# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Tests for ``average_over``.

A parameter listed there stops being part of a graph's identity, so results
that differ only in it land in one series instead of several, and where two of
them fall on the same commit their values are averaged.  It is a view over the
published site: nothing in ``results_dir`` is touched, and removing the key and
republishing brings the separate series back.

The motivating case is ``pythons`` being left unset, so that upgrading the
interpreter on the benchmark machine would otherwise split every graph.
"""

import datetime
import os
from hashlib import sha256
from os.path import isdir, isfile, join

import pytest

from asv import config, runner, util
from asv.repo import get_repo
from asv.results import Results

from . import tools

BENCHMARK_VERSION = sha256(b'time_func').hexdigest()


def _write_result(conf, repo, commit, python, value):
    result = Results(
        {'machine': 'tarzan', 'python': python},
        {},
        commit,
        repo.get_date_from_name(commit),
        python,
        f'conda-py{python}',
        {},
    )
    result.add_result(
        {'name': 'time_func', 'version': BENCHMARK_VERSION, 'params': []},
        runner.BenchmarkResult(
            result=[value],
            samples=[None],
            number=[None],
            errcode=0,
            stderr='',
            profile=None,
        ),
        started_at=datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        duration=1.0,
    )
    result.save(conf.results_dir)


def _conf(tmpdir, dvcs, **extra):
    result_dir = join(tmpdir, 'results')
    if not isdir(join(result_dir, 'tarzan')):
        os.makedirs(join(result_dir, 'tarzan'))
    conf = config.Config.from_json(
        {
            'results_dir': result_dir,
            'html_dir': join(tmpdir, 'html'),
            'repo': dvcs.path,
            'project': 'asv',
            'branches': [util.git_default_branch()],
            **extra,
        }
    )
    util.write_json(
        join(result_dir, 'tarzan', 'machine.json'), {'machine': 'tarzan', 'version': 1}
    )
    return conf


def _write_benchmarks(conf):
    util.write_json(
        join(conf.results_dir, 'benchmarks.json'),
        {
            'time_func': {
                'name': 'time_func',
                'params': [],
                'param_names': [],
                'version': BENCHMARK_VERSION,
            }
        },
        api_version=2,
    )


@pytest.fixture
def upgraded_interpreter(tmpdir):
    # Three commits on 3.13, then three on 3.14 after the machine was upgraded.
    tmpdir = str(tmpdir)
    os.chdir(tmpdir)
    dvcs = tools.generate_repo_from_ops(tmpdir, 'git', [('commit', i) for i in range(6)])
    commits = list(reversed(dvcs.get_branch_hashes()))
    conf = _conf(tmpdir, dvcs)
    repo = get_repo(conf)
    for i, commit in enumerate(commits):
        _write_result(conf, repo, commit, '3.13' if i < 3 else '3.14', 1.0 + i)
    _write_benchmarks(conf)
    return conf, tmpdir


def _graph_dir(tmpdir, *parts):
    return join(tmpdir, 'html', 'graphs', f'branch-{util.git_default_branch()}', *parts)


def test_defaults_to_averaging_over_nothing():
    conf = config.Config.from_json({'repo': '.', 'project': 'x'})
    assert conf.average_over == []


def test_accepts_a_bare_string():
    conf = config.Config.from_json({'repo': '.', 'project': 'x', 'average_over': 'python'})
    assert conf.average_over == ['python']


def test_rejects_non_strings():
    with pytest.raises(util.UserError, match='average_over'):
        config.Config.from_json({'repo': '.', 'project': 'x', 'average_over': [3.14]})


def test_recorded_python_splits_the_graphs(upgraded_interpreter):
    conf, tmpdir = upgraded_interpreter

    tools.run_asv_with_conf(conf, 'publish')

    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['python'] == ['3.13', '3.14']
    for python in ['3.13', '3.14']:
        assert isfile(_graph_dir(tmpdir, 'machine-tarzan', f'python-{python}', 'time_func.json'))


def test_averaging_over_python_joins_them(upgraded_interpreter):
    conf, tmpdir = upgraded_interpreter
    conf.average_over = ['python']

    tools.run_asv_with_conf(conf, 'publish')

    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert 'python' not in index['params']
    assert index['graph_param_list'] == [
        {'branch': util.git_default_branch(), 'machine': 'tarzan'}
    ]
    data = util.load_json(_graph_dir(tmpdir, 'machine-tarzan', 'time_func.json'))
    assert [point[1] for point in data] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_results_on_disk_are_untouched(upgraded_interpreter):
    # The whole point: this is a view, so the recorded data still says which
    # interpreter each measurement came from.
    conf, tmpdir = upgraded_interpreter
    conf.average_over = ['python']
    before = sorted(os.listdir(join(conf.results_dir, 'tarzan')))

    tools.run_asv_with_conf(conf, 'publish')

    assert sorted(os.listdir(join(conf.results_dir, 'tarzan'))) == before
    pythons = {
        Results.load(join(conf.results_dir, 'tarzan', name)).params.get('python')
        for name in before
        if name != 'machine.json'
    }
    assert pythons == {'3.13', '3.14'}

    # ... and dropping the key brings the separate series back.
    conf.average_over = []
    tools.run_asv_with_conf(conf, 'publish')
    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['python'] == ['3.13', '3.14']


def test_two_interpreters_on_one_commit_are_averaged(tmpdir):
    tmpdir = str(tmpdir)
    os.chdir(tmpdir)
    dvcs = tools.generate_repo_from_ops(tmpdir, 'git', [('commit', 0)])
    commit = dvcs.get_branch_hashes()[0]
    conf = _conf(tmpdir, dvcs, average_over=['python'])
    repo = get_repo(conf)
    for python, value in [('3.13', 10.0), ('3.14', 20.0)]:
        _write_result(conf, repo, commit, python, value)
    _write_benchmarks(conf)

    tools.run_asv_with_conf(conf, 'publish')

    data = util.load_json(_graph_dir(tmpdir, 'machine-tarzan', 'time_func.json'))
    assert [point[1] for point in data] == [15.0]
