# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, exists, join
import shutil

import six

from asv import config
from asv import results
from asv.commands import Rm


def test_rm(tmpdir):
    tmpdir = six.text_type(tmpdir)

    shutil.copytree(
        join(dirname(__file__), 'example_results'),
        join(tmpdir, 'example_results'))

    conf = config.Config.from_json({
        'results_dir': join(tmpdir, 'example_results'),
        'repo': "https://github.com/astropy/astropy.git"
        })

    Rm.run(conf, ['benchmark=time_quantity*'])

    results_a = list(results.iter_results(tmpdir))
    for result in results_a:
        for key in six.iterkeys(result.results):
            assert not key.startswith('time_quantity')

    Rm.run(conf, ['commit_hash=05d283b9'])

    results_b = list(results.iter_results(tmpdir))
    assert len(results_b) == len(results_a) - 1
