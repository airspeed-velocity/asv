# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

import six

from asv import environment
from asv import results


def test_results(tmpdir):
    envdir = six.text_type(tmpdir.join("env"))
    version = "{0[0]}.{0[1]}".format(sys.version_info)
    env = environment.get_environment(envdir, version, {})

    resultsdir = six.text_type(tmpdir.join("results"))
    for i in six.moves.xrange(10):
        r = results.Results(
            {'machine': 'foo',
             'arch': 'x86_64'},
            env,
            hex(i),
            i * 1000000)
        for key, val in {
            'suite1.benchmark1': float(i * 0.001),
            'suite1.benchmark2': float(i * i * 0.001),
            'suite2.benchmark1': float((i + 1) ** -1)}.items():
            r.add_time(key, val)
        r.save(resultsdir)

        r2 = results.Results.load(
            os.path.join(resultsdir, r._filename))

        assert r2._results == r._results
        assert r2.date == r.date
        assert r2.commit_hash == r.commit_hash
