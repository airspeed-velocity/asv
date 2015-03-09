# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import re
from os.path import abspath, dirname, join
import shutil
import pytest
from io import StringIO

import six

from asv import config
from asv.commands.dev import Dev
from asv.commands.profiling import Profile
from asv.commands.run import Run

from . import tools


@pytest.fixture
def basic_conf(tmpdir):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    shutil.copyfile(join(local, 'asv-machine.json'),
                    join(tmpdir, 'asv-machine.json'))

    conf = config.Config.from_json({
        'env_dir': join(tmpdir, 'env'),
        'benchmark_dir': join(local, 'benchmark'),
        'results_dir': join(tmpdir, 'results_workflow'),
        'html_dir': join(tmpdir, 'html'),
        'repo': tools.generate_test_repo(tmpdir),
        'project': 'asv',
        'matrix': {
            "six": [None],
            "psutil": ["1.2", "2.1"]
        }
    })

    return tmpdir, local, conf


def test_dev(basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Dev runs
    s = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = s
        Dev.run(conf, _machine_file=join(tmpdir, 'asv-machine.json'))
    finally:
        sys.stdout = stdout

    s.seek(0)
    text = s.read()

    # time_with_warnings failure case
    assert re.search("File.*time_exception.*RuntimeError", text, re.S)
    assert re.search(r"Running time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_run_python_same(basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Run runs with python=same
    s = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = s
        Run.run(conf, _machine_file=join(tmpdir, 'asv-machine.json'), python="same")
    finally:
        sys.stdout = stdout

    s.seek(0)
    text = s.read()

    assert re.search("time_exception.*failed", text, re.S)
    assert re.search(r"Running time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_profile_python_same(basic_conf):
    tmpdir, local, conf = basic_conf

    if sys.version_info[0] == 2:
        # pstats.Profile prints stuff to stdout as bytes
        from StringIO import StringIO as StringIO_py2
        s = StringIO_py2()
    else:
        s = StringIO()

    # Test Profile can run with python=same
    stdout = sys.stdout
    try:
        sys.stdout = s
        Profile.run(conf, "time_secondary.track_value",
                    _machine_file=join(tmpdir, 'asv-machine.json'),
                    python="same")
    finally:
        sys.stdout = stdout

    s.seek(0)
    text = s.read()

    # time_with_warnings failure case
    assert re.search(r"^\s+1\s+.*time_secondary.*\(track_value\)", text, re.M)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


if __name__ == '__main__':
    test_dev('/tmp')
