# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import six

from . import tools
from .test_publish import generate_result_dir


def test_gh_pages(tmpdir, generate_result_dir, monkeypatch):
    tmpdir = os.path.abspath(six.text_type(tmpdir))

    monkeypatch.setenv('EMAIL', 'test@asv')
    monkeypatch.setenv('GIT_COMMITTER_NAME', 'asv test')
    monkeypatch.setenv('GIT_AUTHOR_NAME', 'asv test')

    conf, repo, commits = generate_result_dir([1, 2, 3, 4])

    dvcs_dir = os.path.join(tmpdir, 'repo1')
    dvcs_dir2 = os.path.join(tmpdir, 'repo2')

    os.makedirs(dvcs_dir)

    os.chdir(dvcs_dir)

    dvcs = tools.Git(dvcs_dir)
    dvcs.init()

    open(os.path.join(dvcs_dir, 'dummy'), 'wb').close()

    dvcs.add('dummy')
    dvcs.commit('Initial commit')

    # Check with no existing gh-pages branch, no push
    tools.run_asv_with_conf(conf, "gh-pages", "--no-push")
    dvcs.checkout('gh-pages')
    assert os.path.isfile(os.path.join(dvcs_dir, 'index.html'))
    dvcs.checkout('master')
    assert not os.path.isfile(os.path.join(dvcs_dir, 'index.html'))

    # Check with existing (and checked out) gh-pages branch
    tools.run_asv_with_conf(conf, "gh-pages", "--no-push")
    dvcs.checkout('gh-pages')
    assert os.path.isfile(os.path.join(dvcs_dir, 'index.html'))
    dvcs.checkout('master')

    # Check that the push option works
    dvcs.run_git(['branch', '-D', 'gh-pages'])
    dvcs.run_git(['clone', dvcs_dir, dvcs_dir2])

    os.chdir(dvcs_dir2)
    tools.run_asv_with_conf(conf, "gh-pages")

    os.chdir(dvcs_dir)
    dvcs.checkout('gh-pages')
    assert os.path.isfile(os.path.join(dvcs_dir, 'index.html'))
