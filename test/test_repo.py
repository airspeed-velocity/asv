# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import join

import six
import pytest

from asv import config
from asv import repo
from asv.branch_cache import BranchCache

try:
    import hglib
except ImportError:
    hglib = None

from . import tools


def _test_generic_repo(conf, tmpdir, hash_range, master, branch):
    workcopy_dir = join(tmpdir, "workcopy")

    r = repo.get_repo(conf)

    r.checkout(workcopy_dir, master)
    r.checkout(workcopy_dir, branch)
    r.checkout(workcopy_dir, master)

    hashes = r.get_hashes_from_range(hash_range)
    assert len(hashes) == 4

    dates = [r.get_date(hash) for hash in hashes]
    assert dates == sorted(dates)[::-1]

    tags = r.get_tags()
    for tag in tags:
        r.get_date_from_name(tag)


def _test_branches(conf, branch_commits):
    r = repo.get_repo(conf)
    branch_cache = BranchCache(conf, r)

    assert len(conf.branches) == 2

    commit_branches = {}

    for branch in conf.branches:
        commits = branch_cache.get_branch_commits(branch)

        for commit in branch_commits[branch]:
            assert commit in commits
            commit_branches[commit] = branch


    for commit, branch in commit_branches.items():
        assert branch in branch_cache.get_branches(commit)


def test_repo_git(tmpdir):
    tmpdir = six.text_type(tmpdir)

    conf = config.Config()

    dvcs = tools.generate_test_repo(tmpdir, list(range(10)), dvcs_type='git',
                                    extra_branches=[('master~4', 'some-branch',[11, 12, 13])])

    conf.project = join(tmpdir, "repo")
    conf.repo = dvcs.path
    _test_generic_repo(conf, tmpdir, 'master~4..master', 'master', 'tag5')

    conf.branches = ['master', 'some-branch']
    branch_commits = {
        'master': [dvcs.get_hash('master'), dvcs.get_hash('master~6')],
        'some-branch': [dvcs.get_hash('some-branch'), dvcs.get_hash('some-branch~6')]
    }
    _test_branches(conf, branch_commits)


@pytest.mark.skipif(hglib is None,
                    reason="needs hglib")
def test_repo_hg(tmpdir):
    tmpdir = six.text_type(tmpdir)

    conf = config.Config()

    dvcs = tools.generate_test_repo(tmpdir, list(range(10)), dvcs_type='hg', 
                                    extra_branches=[('default~4', 'some-branch',[11, 12, 13])])

    conf.project = join(tmpdir, "repo")
    conf.repo = dvcs.path
    _test_generic_repo(conf, tmpdir, hash_range="tip:-4",
                       master="tip", branch="tag5")

    conf.branches = ['default', 'some-branch']
    branch_commits = {
        'default': [dvcs.get_hash('default'), dvcs.get_hash('default~6')],
        'some-branch': [dvcs.get_hash('some-branch'), dvcs.get_hash('some-branch~6')]
    }
    _test_branches(conf, branch_commits)
