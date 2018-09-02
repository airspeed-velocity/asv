# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, join

import six
import textwrap

from asv import config

from . import tools


RESULT_DIR = abspath(join(dirname(__file__), 'example_results'))
BENCHMARK_DIR = abspath(join(dirname(__file__), 'example_results'))
MACHINE_FILE = abspath(join(dirname(__file__), 'asv-machine.json'))


def test_show(capsys, tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'results_dir': RESULT_DIR,
         'repo': tools.generate_test_repo(tmpdir).path,
         'project': 'asv',
         'environment_type': "shouldn't matter what"})

    tools.run_asv_with_conf(conf, 'show')
    text, err = capsys.readouterr()
    assert 'py2.7-Cython-numpy1.8' in text
    assert 'py2.7-numpy1.8' in text
    assert 'py2.7-foo-numpy1.8' in text
    assert 'fcf8c079' in text

    tools.run_asv_with_conf(conf, 'show', 'fcf8c079')
    text, err = capsys.readouterr()
    assert "time_ci_small [cheetah/py2.7-numpy1.8]\n  3.00±0s\n\n" in text

    tools.run_asv_with_conf(conf, 'show', 'fcf8c079', '--machine=cheetah',
                            '--bench=time_ci', '--details')
    text, err = capsys.readouterr()
    expected = textwrap.dedent("""
    Commit: fcf8c079

    time_ci_big [cheetah/py2.7-numpy1.8]
      3.00±1s
      ci_99: (1.50s, 3.50s)

    time_ci_small [cheetah/py2.7-numpy1.8]
      3.00±0s
      ci_99: (3.10s, 3.90s)
    """)
    assert text.strip() == expected.strip()
