# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import glob
from io import StringIO
import os
from os.path import abspath, dirname, join, isfile
import shutil
import sys

import six
import json
import pytest

from asv import config
from asv.commands.run import Run
from asv.commands.publish import Publish
from asv.commands.find import Find
from asv.commands.continuous import Continuous
from asv.util import check_output, which

from . import tools


dummy_values = [
    (None, None),
    (1, 1),
    (3, 1),
    (None, 1),
    (6, None),
    (5, 1),
    (6, 1),
    (6, 1),
    (6, 6),
    (6, 6),
]


@pytest.fixture
def basic_conf(tmpdir):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    machine_file = join(tmpdir, 'asv-machine.json')

    shutil.copyfile(join(local, 'asv-machine.json'),
                    machine_file)

    repo_path = tools.generate_test_repo(tmpdir, dummy_values)

    conf = config.Config.from_json({
        'env_dir': join(tmpdir, 'env'),
        'benchmark_dir': join(local, 'benchmark'),
        'results_dir': join(tmpdir, 'results_workflow'),
        'html_dir': join(tmpdir, 'html'),
        'repo': repo_path,
        'dvcs': 'git',
        'project': 'asv',
        'matrix': {
            "six": [None],
            "psutil": ["1.2", "2.1"]
        }
    })

    return tmpdir, local, conf, machine_file


def test_run_publish(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Tests a typical complete run/publish workflow
    Run.run(conf, range_spec="master~5..master", steps=2,
            _machine_file=machine_file, quick=True)

    assert len(os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results_workflow'))) == 2

    Publish.run(conf)

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))

    # Check parameterized test json data format
    filename = glob.glob(join(tmpdir, 'html', 'graphs', 'arch-x86_64', 'branch-master',
                              'cpu-Blazingly fast', 'machine-orangutan', 'os-GNU',
                              'Linux', 'psutil-2.1', 'python-*', 'ram-128GB',
                              'six', 'params_examples.time_skip.json'))[0]
    with open(filename, 'r') as fp:
        data = json.load(fp)
        assert len(data) == 2
        assert isinstance(data[0][0], int)  # date
        assert len(data[0][1]) == 3
        assert len(data[1][1]) == 3
        assert isinstance(data[0][1][0], float)
        assert isinstance(data[0][1][1], float)
        assert data[0][1][2] is None

    # Check that the skip options work
    s = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = s
        Run.run(conf, range_spec="master~5..master", steps=2,
                _machine_file=join(tmpdir, 'asv-machine.json'), quick=True,
                skip_successful=True, skip_failed=True)
        Run.run(conf, range_spec="master~5..master", steps=2,
                _machine_file=join(tmpdir, 'asv-machine.json'), quick=True,
                skip_existing_commits=True)
    finally:
        sys.stdout = stdout
    s.seek(0)
    text = s.read()
    assert 'Running benchmarks.' not in text

    # Check EXISTING works
    Run.run(conf, range_spec="EXISTING",
            _machine_file=machine_file, quick=True)

    # Remove the benchmarks.json file to make sure publish can
    # regenerate it

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    Publish.run(conf)


def test_continuous(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Check that asv continuous runs
    s = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = s
        Continuous.run(conf, branch="master^", _machine_file=machine_file, show_stderr=True)
    finally:
        sys.stdout = stdout

    s.seek(0)
    text = s.read()
    assert "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY" in text
    assert "params_examples.track_find_test(2)              1.0        6.0   6.00000000x" in text
    assert "params_examples.ClassOne" in text


def test_find(basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    # Test find at least runs
    s = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = s
        Find.run(conf, "master~5..master", "params_examples.track_find_test",
                 _machine_file=machine_file)
    finally:
        sys.stdout = stdout

    # Check it found the first commit after the initially tested one
    s.seek(0)
    output = s.read()

    regression_hash = check_output(
        [which('git'), 'rev-parse', 'master^'], cwd=conf.repo)

    assert "Greatest regression found: {0}".format(regression_hash[:8]) in output


if __name__ == '__main__':
    from asv import console
    console.log.enable()

    from asv import machine
    machine.Machine.hardcoded_machine_name = 'orangutan'

    test_workflow('/tmp')
