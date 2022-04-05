# Licensed under a 3-clause BSD style license - see LICENSE.rst

import re

from asv.commands import make_argparser

from . import tools


def test_dev(capsys, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Test Dev runs (with full benchmark suite)
    ret = tools.run_asv_with_conf(conf, 'dev', '--quick', '-e',
                                  _machine_file=machine_file)
    assert ret is None
    text, err = capsys.readouterr()

    # time_with_warnings failure case
    assert re.search("File.*time_exception.*RuntimeError", text, re.S)
    assert re.search(r"time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_dev_with_repo_subdir(capsys, basic_conf_with_subdir):
    """
    Same as test_dev, but with the Python project inside a subdirectory.
    """
    tmpdir, local, conf, machine_file = basic_conf_with_subdir

    # Test Dev runs
    tools.run_asv_with_conf(conf, 'dev', '--quick',
                            '--bench=time_secondary.track_value',
                            _machine_file=machine_file)
    text, err = capsys.readouterr()

    # Benchmarks were found and run
    assert re.search(r"time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_dev_strict(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf
    ret = tools.run_asv_with_conf(conf, 'dev', '--quick',
                                  '--bench=TimeSecondary',
                                  _machine_file=machine_file)
    assert ret == 2


def test_run_python_same(capsys, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Test Run runs with python=same
    tools.run_asv_with_conf(conf, 'run', '--python=same',
                            '--bench=time_secondary.TimeSecondary.time_exception',
                            '--bench=time_secondary.track_value',
                            _machine_file=machine_file)
    text, err = capsys.readouterr()

    assert re.search("time_exception.*failed", text, re.S)
    assert re.search(r"time_secondary.track_value\s+42.0", text)

    # Check that it did not clone or install
    assert "Cloning" not in text
    assert "Installing" not in text


def test_profile_python_same(capsys, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Test Profile can run with python=same
    tools.run_asv_with_conf(conf, 'profile', '--python=same', "time_secondary.track_value",
                            _machine_file=machine_file)
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
