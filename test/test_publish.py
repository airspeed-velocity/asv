# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, join, isfile, isdir
import shutil

import six

from asv import config
from asv.commands.publish import Publish
from asv import util


from . import tools

RESULT_DIR = abspath(join(dirname(__file__), 'example_results'))
BENCHMARK_DIR = abspath(join(dirname(__file__), 'benchmark'))


def test_publish(tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    result_dir = join(tmpdir, 'sample_results')
    os.makedirs(result_dir)
    os.makedirs(join(result_dir, 'cheetah'))

    # Synthesize history with two branches that both have commits
    result_files = [fn for fn in os.listdir(join(RESULT_DIR, 'cheetah'))
                    if fn.endswith('.json') and fn != 'machine.json']
    master_values = list(range(len(result_files)*2//3))
    branch_values = list(range(len(master_values), len(result_files)))
    dvcs = tools.generate_test_repo(tmpdir, master_values, 'git',
                                    [('master~6', 'some-branch', branch_values)])

    # Copy and modify result files, fixing commit hashes and setting result
    # dates to distinguish the two branches
    master_commits = dvcs.get_branch_hashes('master')
    only_branch = [x for x in dvcs.get_branch_hashes('some-branch')
                   if x not in master_commits]
    commits = master_commits + only_branch
    for k, item in enumerate(zip(result_files, commits)):
        fn, commit = item
        src = join(RESULT_DIR, 'cheetah', fn)
        dst = join(result_dir, 'cheetah', commit[:8] + fn[8:])
        data = util.load_json(src, cleanup=False)
        data['commit_hash'] = commit
        if commit in only_branch:
            data['date'] = -k
        else:
            data['date'] = k
        util.write_json(dst, data)

    shutil.copyfile(join(RESULT_DIR, 'benchmarks.json'),
                    join(result_dir, 'benchmarks.json'))
    shutil.copyfile(join(RESULT_DIR, 'cheetah', 'machine.json'),
                    join(result_dir, 'cheetah', 'machine.json'))


    # Publish the synthesized data
    conf = config.Config.from_json(
        {'benchmark_dir': BENCHMARK_DIR,
         'results_dir': result_dir,
         'html_dir': join(tmpdir, 'html'),
         'repo': dvcs.path,
         'project': 'asv'})

    Publish.run(conf)

    # Check output
    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))
    assert not isdir(join(tmpdir, 'html', 'graphs', 'Cython', 'arch-x86_64',
                          'branch-some-branch'))
    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['branch'] == ['master']

    def check_file(branch):
        fn = join(tmpdir, 'html', 'graphs', 'Cython', 'arch-x86_64', 'branch-' + branch,
                  'cpu-Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)',
                  'machine-cheetah', 'numpy-1.8', 'os-Linux (Fedora 20)', 'python-2.7', 'ram-8.2G',
                  'time_coordinates.time_latitude.json')
        data = util.load_json(fn, cleanup=False)
        if branch == 'master':
            # we set all dates positive for master above
            assert all(x[0] >= 0 for x in data)
        else:
            # we set some dates negative for some-branch above
            assert any(x[0] < 0 for x in data) and any(x[0] >= 0 for x in data)

    check_file("master")

    # Publish with branches set in the config
    conf.branches = ['master', 'some-branch']
    Publish.run(conf)

    # Check output
    check_file("master")
    check_file("some-branch")

    index = util.load_json(join(tmpdir, 'html', 'index.json'))
    assert index['params']['branch'] == ['master', 'some-branch']
