# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import re
from os.path import abspath, dirname, join, relpath
import shutil
import pytest

import six

from asv import config
from asv.commands import make_argparser

from . import tools


@pytest.fixture
def basic_conf(tmpdir):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    # Use relative paths on purpose since this is what will be in
    # actual config files

    shutil.copytree(os.path.join(local, 'benchmark'), 'benchmark')

    shutil.copyfile(join(local, 'asv-machine.json'),
                    join(tmpdir, 'asv-machine.json'))

    conf = config.Config.from_json({
        'env_dir': 'env',
        'benchmark_dir': 'benchmark',
        'results_dir': 'results_workflow',
        'html_dir': 'html',
        'repo': relpath(tools.generate_test_repo(tmpdir).path),
        'project': 'asv',
        'matrix': {
            "six": [None],
            "colorama": ["0.3.6", "0.3.7"]
        }
    })

    return tmpdir, local, conf


def test_dev(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Dev runs
    tools.run_asv_with_conf(conf, 'dev', _machine_file=join(tmpdir, 'asv-machine.json'))
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
    tools.run_asv_with_conf(conf, 'run', '--python=same', _machine_file=join(tmpdir, 'asv-machine.json'))
    text, err = capsys.readouterr()

    assert re.search("time_exception.*failed", text, re.S)
    assert re.search(r"Running time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_profile_python_same(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test Profile can run with python=same
    tools.run_asv_with_conf(conf, 'profile', '--python=same', "time_secondary.track_value",
                            _machine_file=join(tmpdir, 'asv-machine.json'))
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
    assert args.env_spec == []
    assert not args.verbose

    argv = ['dev', '--python=foo']
    args = parser.parse_args(argv)
    assert args.env_spec == [':foo']

    argv = ['dev', '-E', 'existing:foo']
    args = parser.parse_args(argv)
    assert args.env_spec == ['existing:foo']

    argv = ['run', 'ALL']
    args = parser.parse_args(argv)
    assert args.env_spec == []

    argv = ['--verbose', '--config=foo', 'dev']
    args = parser.parse_args(argv)
    assert args.verbose
    assert args.config == 'foo'

    argv = ['dev', '--verbose', '--config=foo']
    args = parser.parse_args(argv)
    assert args.verbose
    assert args.config == 'foo'


def test_run_steps_arg():
    parser, subparsers = make_argparser()

    argv = ['run', '--steps=20', 'ALL']
    args = parser.parse_args(argv)
    assert args.steps == 20


if __name__ == '__main__':
    test_dev('/tmp')
