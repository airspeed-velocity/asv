# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import isfile, join

import six

from . import tools
from asv import util
import asv.commands.quickstart


def test_quickstart(tmpdir):
    tmpdir = six.text_type(tmpdir)

    dest = join(tmpdir, 'separate')
    os.makedirs(dest)

    tools.run_asv('quickstart', '--no-top-level', '--dest', dest)

    assert isfile(join(dest, 'asv.conf.json'))
    assert isfile(join(dest, 'benchmarks', 'benchmarks.py'))
    conf = util.load_json(join(dest, 'asv.conf.json'))
    assert 'env_dir' not in conf
    assert 'html_dir' not in conf
    assert 'results_dir' not in conf

    dest = join(tmpdir, 'same')
    os.makedirs(dest)

    try:
        asv.commands.quickstart.raw_input = lambda msg: '1'
        tools.run_asv('quickstart', '--dest', dest)
    finally:
        del asv.commands.quickstart.raw_input

    assert isfile(join(dest, 'asv.conf.json'))
    assert isfile(join(dest, 'benchmarks', 'benchmarks.py'))
    conf = util.load_json(join(dest, 'asv.conf.json'))
    assert conf['env_dir'] != 'env'
    assert conf['html_dir'] != 'html'
    assert conf['results_dir'] != 'results'
