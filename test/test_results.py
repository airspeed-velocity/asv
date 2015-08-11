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
