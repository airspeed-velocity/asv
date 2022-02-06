# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import dirname, join
import shutil

import six

from asv import config
from asv import results

from . import tools
from .tools import example_results


def test_rm(tmpdir, example_results):
    tmpdir = six.text_type(tmpdir)

    shutil.copytree(
        example_results,
        join(tmpdir, 'example_results'))

    conf = config.Config.from_json({
        'results_dir': join(tmpdir, 'example_results'),
        'repo': "### IGNORED, BUT REQUIRED ###"
        })

    tools.run_asv_with_conf(conf, 'rm', '-y', 'benchmark=time_quantity*')

    results_a = list(results.iter_results(tmpdir))
    for result in results_a:
        for key in result.get_all_result_keys():
            assert not key.startswith('time_quantity')
        for key in six.iterkeys(result.started_at):
            assert not key.startswith('time_quantity')
        for key in six.iterkeys(result.duration):
            assert not key.startswith('time_quantity')

    tools.run_asv_with_conf(conf, 'rm', '-y', 'commit_hash=05d283b9')

    results_b = list(results.iter_results(tmpdir))
    assert len(results_b) == len(results_a) - 1
