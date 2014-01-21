# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import join, exists

import six

from asv import config
from asv.commands import Publish

RESULT_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'example_results'))


def test_publish(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'results_dir': RESULT_DIR,
         'html_dir': join(tmpdir, 'html'),
         'repo': 'https://github.com/spacetelescope/asv.git',
         'project': 'asv'})

    Publish.run(conf)

    assert exists(join(tmpdir, 'html', 'index.html'))
    assert exists(join(tmpdir, 'html', 'index.json'))
    assert exists(join(tmpdir, 'html', 'asv.js'))
    assert exists(join(tmpdir, 'html', 'asv.css'))
