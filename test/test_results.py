# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import join

import six

from asv import results, util
import pytest


def test_results(tmpdir):
    tmpdir = six.text_type(tmpdir)

    resultsdir = join(tmpdir, "results")
    for i in six.moves.xrange(10):
        r = results.Results(
            {'machine': 'foo',
             'arch': 'x86_64'},
            {},
            hex(i),
            i * 1000000,
            '2.7')
        for key, val in {
            'suite1.benchmark1': float(i * 0.001),
            'suite1.benchmark2': float(i * i * 0.001),
            'suite2.benchmark1': float((i + 1) ** -1)}.items():
            r.add_time(key, val)
        r.save(resultsdir)

        r2 = results.Results.load(join(resultsdir, r._filename))

        assert r2._results == r._results
        assert r2.date == r.date
        assert r2.commit_hash == r.commit_hash


def test_get_result_hash_from_prefix(tmpdir):
    results_dir = tmpdir.mkdir('results')
    machine_dir = results_dir.mkdir('machine')

    for f in ['e5b6cdbc', 'e5bfoo12']:
        open(join(str(machine_dir), '{0}-py2.7-Cython-numpy1.8.json'.format(f)), 'a').close()

    # check unique, valid case
    full_commit = results.get_result_hash_from_prefix(str(results_dir), 'machine', 'e5b6')
    assert full_commit == 'e5b6cdbc'

    # check invalid hash case
    bad_commit = results.get_result_hash_from_prefix(str(results_dir), 'machine', 'foobar')
    assert bad_commit is None

    # check non-unique case
    with pytest.raises(util.UserError) as excinfo:
        results.get_result_hash_from_prefix(str(results_dir), 'machine', 'e')

    assert 'one of multiple commits' in str(excinfo.value)


def test_minimum_of_results():
    nan = float('nan')

    param_res_1 = dict(params=[[1, 2], [3, 4]],
                       result=[1, 1, 1, 1])
    param_res_2 = dict(params=[[1, 2], [3, 4]],
                       result=[2, 2, 2, 2])
    param_res_2_incomp = dict(params=[[1, 2, 3], [3, 4, 5]],
                              result=[2, 2, 9,
                                      2, 2, 9,
                                      9, 9, 9,
                                      9, 9, 9])
    param_res_1_incomp = dict(params=[[1, 2, 3], [3, 4, 5]],
                              result=[1, 1, 9,
                                      1, 1, 9,
                                      9, 9, 9,
                                      9, 9, 9])
    param_res_incomp = dict(params=[['a', 'b', 'c']], result=[1, 1, 1])
    param_res_1_nan = dict(params=[[1, 2], [3, 4]],
                           result=[1, nan, 1, nan])
    param_res_1_none = dict(params=[[1, 2], [3, 4]],
                            result=[1, None, None, 1])
    param_res_malform1 = dict(paramx=param_res_1['params'], result=param_res_1['result'])
    param_res_malform2 = dict(params=param_res_1['params'], resultx=param_res_1['result'])

    datasets = [
        # no result
        (None, None, None),
        (None, nan, None),
        (nan, None, nan),
        (nan, nan, nan),
        (None, 1, None),
        (None, 1.0, None),
        (nan, 1, nan),
        (nan, 1.0, nan),
        (nan, 1, nan),
        (None, param_res_1, None),
        (nan, param_res_1, nan),
        (param_res_1, None, param_res_1),
        (param_res_1, nan, param_res_1),
        # float/int
        (1, 2, 1),
        (1.0, 2, 1.0),
        (1, 2.0, 1),
        (1.0, 2.0, 1.0),
        (2, 1, 1),
        (2, 1.0, 1.0),
        (2.0, 1, 1),
        (2.0, 1.0, 1.0),
        # parameterized results, malformed
        (param_res_1, 3, param_res_1),
        (3, param_res_1, 3),
        (param_res_malform1, param_res_2, param_res_malform1),
        (param_res_malform2, param_res_2, param_res_malform2),
        (param_res_2, param_res_malform1, param_res_2),
        (param_res_2, param_res_malform2, param_res_2),
        (3, param_res_1, 3),
        # parameterized results
        (param_res_1, param_res_2, param_res_1),
        (param_res_2, param_res_1, param_res_1),
        (param_res_1, param_res_2_incomp, param_res_1),
        (param_res_2, param_res_1_incomp, param_res_1),
        (param_res_2, param_res_incomp, param_res_2),
        (param_res_2, param_res_1_none, dict(params=param_res_2['params'],
                                             result=[1, 2, 2, 1])),
        (param_res_2, param_res_1_nan, dict(params=param_res_2['params'],
                                            result=[1, 2, 1, 2])),
        (param_res_1_none, param_res_1, dict(params=param_res_1['params'],
                                             result=[1, None, None, 1])),
        (param_res_1_nan, param_res_1, dict(params=param_res_1['params'],
                                            result=[1, nan, 1, nan])),
        (param_res_1_nan, param_res_1_none, param_res_1_nan),
        (param_res_1_none, param_res_1_nan, param_res_1_none),
    ]

    for a, b, c in datasets:
        d = results.minimum_of_results(a, b)

        if isinstance(d, dict) and d.get('params') and d.get('result'):
            assert d['params'] == c['params'], (a, b, c, d)
            assert len(d['result']) == len(c['result']), (a, b, c, d)
            assert all(x == y or (util.is_nan(x) and util.is_nan(y))
                       for x, y in zip(c['result'], d['result'])), (a, b, c, d)
        else:
            assert d == c or (util.is_nan(d) and util.is_nan(c)), (a, b, c, d)
