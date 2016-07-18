# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import datetime
import shutil
from os.path import join

import six

from asv import results, util
import pytest


def test_results(tmpdir):
    tmpdir = six.text_type(tmpdir)

    timestamp1 = datetime.datetime.utcnow()
    timestamp2 = datetime.datetime.utcnow()

    resultsdir = join(tmpdir, "results")
    for i in six.moves.xrange(10):
        r = results.Results(
            {'machine': 'foo',
             'arch': 'x86_64'},
            {},
            hex(i),
            i * 1000000,
            '2.7',
            'some-environment-name')
        for key, val in {
            'suite1.benchmark1': float(i * 0.001),
            'suite1.benchmark2': float(i * i * 0.001),
            'suite2.benchmark1': float((i + 1) ** -1)}.items():
            r.add_result(key, val, timestamp1, timestamp2)
        r.save(resultsdir)

        r2 = results.Results.load(join(resultsdir, r._filename))

        assert r2._results == r._results
        assert r2.date == r.date
        assert r2.commit_hash == r.commit_hash
        assert r2._filename == r._filename
        assert r.started_at == r._started_at
        assert r.ended_at == r._ended_at


def test_get_result_hash_from_prefix(tmpdir):
    results_dir = tmpdir.mkdir('results')
    machine_dir = results_dir.mkdir('cheetah')

    machine_json = join(os.path.dirname(__file__), 'example_results', 'cheetah', 'machine.json')
    shutil.copyfile(machine_json, join(str(machine_dir), 'machine.json'))

    for f in ['e5b6cdbc', 'e5bfoo12']:
        open(join(str(machine_dir), '{0}-py2.7-Cython-numpy1.8.json'.format(f)), 'a').close()

    # check unique, valid case
    full_commit = results.get_result_hash_from_prefix(str(results_dir), 'cheetah', 'e5b6')
    assert full_commit == 'e5b6cdbc'

    # check invalid hash case
    bad_commit = results.get_result_hash_from_prefix(str(results_dir), 'cheetah', 'foobar')
    assert bad_commit is None

    # check non-unique case
    with pytest.raises(util.UserError) as excinfo:
        results.get_result_hash_from_prefix(str(results_dir), 'cheetah', 'e')

    assert 'one of multiple commits' in str(excinfo.value)


def test_backward_compat_load():
    resultsdir = join(os.path.dirname(__file__), 'example_results')
    filename = join('cheetah', '624da0aa-py2.7-Cython-numpy1.8.json')

    r = results.Results.load(join(resultsdir, filename))
    assert r._filename == filename
    assert r._env_name == 'py2.7-Cython-numpy1.8'


def test_json_timestamp(tmpdir):
    # Check that per-benchmark timestamps are saved as JS timestamps in the result file
    tmpdir = six.text_type(tmpdir)

    stamp0 = datetime.datetime(1970, 1, 1)
    stamp1 = datetime.datetime(1971, 1, 1)
    stamp2 = datetime.datetime.utcnow()

    r = results.Results({'machine': 'mach'}, {}, 'aaaa', util.datetime_to_timestamp(stamp0),
                        'py', 'env')
    r.add_result('some_benchmark', 42, stamp1, stamp2)
    r.save(tmpdir)

    r = util.load_json(join(tmpdir, 'mach', 'aaaa-env.json'))
    assert r['started_at']['some_benchmark'] == util.datetime_to_js_timestamp(stamp1)
    assert r['ended_at']['some_benchmark'] == util.datetime_to_js_timestamp(stamp2)


def test_iter_results(capsys, tmpdir):
    src = os.path.join(os.path.dirname(__file__), 'example_results')
    dst = os.path.join(six.text_type(tmpdir), 'example_results')
    shutil.copytree(src, dst)

    path = os.path.join(dst, 'cheetah')

    skip_list = [
        'machine.json',
        'aaaaaaaa-py2.7-Cython-numpy1.8.json', # malformed file
        'bbbbbbbb-py2.7-Cython-numpy1.8.json', # malformed file
        'cccccccc-py2.7-Cython-numpy1.8.json', # malformed file
    ]

    files = [f for f in os.listdir(path) if f.endswith('.json') and f not in skip_list]
    res = list(results.iter_results(path))
    assert len(res) == len(files)
    out, err = capsys.readouterr()
    assert skip_list[1] in out
    assert skip_list[2] in out
    assert skip_list[3] in out
    assert skip_list[0] not in out

    # The directory should be ignored without machine.json
    os.unlink(os.path.join(path, 'machine.json'))
    res = list(results.iter_results(path))
    assert len(res) == 0
    out, err = capsys.readouterr()
    assert "machine.json" in out
