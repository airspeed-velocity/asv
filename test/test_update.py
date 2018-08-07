# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
import hashlib

from asv import util

from . import tools
from .test_publish import generate_result_dir


def test_update_simple(monkeypatch, generate_result_dir):
    conf, repo, commits = generate_result_dir(5 * [1] + 5 * [10])

    basedir = os.path.abspath(os.path.dirname(conf.results_dir))
    local = os.path.abspath(os.path.dirname(__file__))

    shutil.copyfile(os.path.join(local, 'asv-machine.json'),
                    os.path.join(basedir, 'asv-machine.json'))
    machine_file = 'asv-machine.json'

    conf_values = {}
    for key in ['results_dir', 'html_dir', 'repo', 'project', 'branches']:
        conf_values[key] = getattr(conf, key)

    util.write_json(os.path.join(basedir, 'asv.conf.json'), conf_values,
                    api_version=1)

    # Check renaming of long result files
    machine_dir = os.path.join(basedir, 'results', 'tarzan')

    result_fn = [fn for fn in os.listdir(machine_dir)
                 if fn != 'machine.json'][0]
    long_result_fn = 'abbacaca-' + 'a'*128 + '.json'
    hash_result_fn = ('abbacaca-env-'
                      + hashlib.md5(b'a'*128).hexdigest()
                      + '.json')

    shutil.copyfile(os.path.join(machine_dir, result_fn),
                    os.path.join(machine_dir, long_result_fn))

    # Should succeed
    monkeypatch.chdir(basedir)
    tools.run_asv("update", _machine_file=machine_file)

    # Check file rename
    items = [fn.lower() for fn in os.listdir(machine_dir)]
    assert long_result_fn not in items
    assert hash_result_fn in items
