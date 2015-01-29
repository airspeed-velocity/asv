# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import join, isfile

import six

from asv import config
from asv.commands.publish import Publish

RESULT_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'example_results'))
BENCHMARK_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'benchmark'))


def test_publish(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'benchmark_dir': BENCHMARK_DIR,
         'results_dir': RESULT_DIR,
         'html_dir': join(tmpdir, 'html'),
         'repo': 'https://github.com/spacetelescope/asv.git',
         'project': 'asv'})

    Publish.run(conf)

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))
