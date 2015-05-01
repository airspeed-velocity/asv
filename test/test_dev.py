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

import six

from asv import config
from asv.commands.dev import Dev
from asv.commands.profiling import Profile
from asv.commands.run import Run
from asv.commands import make_argparser

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
        'repo': tools.generate_test_repo(tmpdir).path,
        'project': 'asv',
        'matrix': {
            "six": [None],
            "psutil": ["1.2", "2.1"]
        }
    })

    return tmpdir, local, conf


def test_dev(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Dev runs
    Dev.run(conf, _machine_file=join(tmpdir, 'asv-machine.json'))
    text, err = capsys.readouterr()

    # time_with_warnings failure case
    assert re.search("File.*time_exception.*RuntimeError", text, re.S)
    assert re.search(r"Running time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_run_python_same(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Run runs with python=same
    Run.run(conf, _machine_file=join(tmpdir, 'asv-machine.json'), python="same")
    text, err = capsys.readouterr()

    assert re.search("time_exception.*failed", text, re.S)
    assert re.search(r"Running time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_profile_python_same(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Profile can run with python=same
    Profile.run(conf, "time_secondary.track_value",
                _machine_file=join(tmpdir, 'asv-machine.json'),
                python="same")
    text, err = capsys.readouterr()

    # time_with_warnings failure case
    assert re.search(r"^\s+1\s+.*time_secondary.*\(track_value\)", text, re.M)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_dev_python_arg():
    parser, subparsers = make_argparser()

    argv = ['dev']
    args = parser.parse_args(argv)
    assert args.python == 'same'

    argv = ['dev', '--python=foo']
    args = parser.parse_args(argv)
    assert args.python == 'foo'

    argv = ['run', 'ALL']
    args = parser.parse_args(argv)
    assert args.python is None


def test_run_steps_arg():
    parser, subparsers = make_argparser()

    argv = ['run', '--steps=20', 'ALL']
    args = parser.parse_args(argv)
    assert args.steps == 20


if __name__ == '__main__':
    test_dev('/tmp')
