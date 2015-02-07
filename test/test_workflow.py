# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, exists, join, isfile
import shutil
import glob

import six
import json

from asv import config
from asv.commands.run import Run
from asv.commands.publish import Publish


def test_run_publish(tmpdir):
    # Tests a typical complete run/publish workflow
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
        'repo': os.path.join(local, '..'),
        'dvcs': 'git',
        'project': 'asv',
        'matrix': {
            "six": [None],
            "psutil": ["1.2", "2.1"]
        }
    })

    Run.run(conf, range_spec="6b1fb9b04f..2927a27ec", steps=2,
            _machine_file=join(tmpdir, 'asv-machine.json'), quick=True)

    assert len(os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results_workflow'))) == 2

    Publish.run(conf)

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))

    # Check parameterized test json data format
    filename = glob.glob(os.path.join(tmpdir, 'html', 'graphs', 'arch-x86_64',
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

    # Check EXISTING works
    Run.run(conf, range_spec="EXISTING",
            _machine_file=join(tmpdir, 'asv-machine.json'), quick=True)

    # Remove the benchmarks.json file to make sure publish can
    # regenerate it

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    Publish.run(conf)


if __name__ == '__main__':
    from asv import console
    console.log.enable()

    from asv import machine
    machine.Machine.hardcoded_machine_name = 'orangutan'

    test_workflow('/tmp')
