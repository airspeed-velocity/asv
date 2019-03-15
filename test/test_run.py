# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, join, relpath

import six
import pytest
import shutil

from asv import config
from asv import results
from asv import environment

from . import tools


@pytest.fixture
def basic_conf(tmpdir):
    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    os.chdir(tmpdir)

    shutil.copytree(os.path.join(local, 'benchmark'), 'benchmark')

    shutil.copyfile(join(local, 'asv-machine.json'),
                    join(tmpdir, 'asv-machine.json'))

    repo_path = relpath(tools.generate_test_repo(tmpdir).path)

    conf_dict = {
        'benchmark_dir': 'benchmark',
        'results_dir': 'results_workflow',
        'repo': repo_path,
        'project': 'asv',
        'environment_type': "existing",
        'python': "same"
    }

    conf = config.Config.from_json(conf_dict)

    return tmpdir, conf


def test_run_existing(capsys, basic_conf):
    tmpdir, conf = basic_conf

    commit_label = 'commit_label'

    tools.run_asv_with_conf(conf, 'run', '--commit-label=' + commit_label, _machine_file=join(tmpdir, 'asv-machine.json'))

    env_name = list(environment.get_environments(conf, None))[0].name

    result_filename = commit_label + '-' + env_name + '.json'
    
    assert result_filename in os.listdir(join('results_workflow', 'orangutan'))

    result_path = join('results_workflow', 'orangutan', result_filename)
    times = results.Results.load(result_path)

    assert times.commit_hash == 'label-' + commit_label
