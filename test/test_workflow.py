# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, exists, join

import six

from asv import config
from asv.commands import Run, Publish


def test_workflow(tmpdir):
    # Tests a typical complete run/publish workflow
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    conf = config.Config.from_json({
        'env_dir': join(tmpdir, 'env'),
        'benchmark_dir': join(local, 'benchmark'),
        'results_dir': join(tmpdir, 'results'),
        'html_dir': join(tmpdir, 'html'),
        'repo': 'https://github.com/spacetelescope/asv.git',
        'project': 'asv',
        'matrix': {
            "six": [None],
            "psutil": ["1.2", "1.1"]
        }
    })

    Run.run(conf, range_spec="initial..master", steps=2,
            _machine_file=join(local, 'asv-machine.json'))

    assert len(os.listdir(join(tmpdir, 'results', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results'))) == 2

    Publish.run(conf)

    assert exists(join(tmpdir, 'html', 'index.html'))
    assert exists(join(tmpdir, 'html', 'index.json'))
    assert exists(join(tmpdir, 'html', 'asv.js'))
    assert exists(join(tmpdir, 'html', 'asv.css'))

    Run.run(conf, range_spec="existing",
            _machine_file=join(local, 'asv-machine.json'))

    # Remove the benchmarks.json file to make sure publish can
    # regenerate it

    os.remove(join(tmpdir, "results", "benchmarks.json"))

    Publish.run(conf)


if __name__ == '__main__':
    from asv import console
    console.console.enable()

    from asv import machine
    machine.Machine.hardcoded_machine_name = 'orangutan'

    test_workflow('/tmp')
