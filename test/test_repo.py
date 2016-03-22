# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import join

import six
import pytest
import tempfile
import shutil
import pytest

from asv import config
from asv import repo
from asv import util
from asv.branch_cache import BranchCache

try:
    import hglib
except ImportError:
    hglib = None

from . import tools


def _test_generic_repo(conf, tmpdir, hash_range, master, branch, is_remote=False):
    workcopy_dir = tempfile.mkdtemp(dir=tmpdir, prefix="workcopy")
    os.rmdir(workcopy_dir)

    # check mirroring fails early if *mirror_dir* exists but is not
    # a mirror
    if is_remote:
        if os.path.isdir(conf.project):
            shutil.rmtree(conf.project)
        os.makedirs(join(conf.project, 'hello'))
        with pytest.raises(util.UserError):
            r = repo.get_repo(conf)
        shutil.rmtree(conf.project)

    # basic checkouts
    r = repo.get_repo(conf)

    r.checkout(workcopy_dir, master)
    r.checkout(workcopy_dir, branch)
    r.checkout(workcopy_dir, master)

    # check recovering from corruption
    for pth in ['.hg', '.git']:
        pth = os.path.join(workcopy_dir, pth)
        if os.path.isdir(pth):
            shutil.rmtree(pth)
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

    dvcs = tools.generate_test_repo(tmpdir, list(range(10)), dvcs_type='git',
                                    extra_branches=[('master~4', 'some-branch',[11, 12, 13])])

    mirror_dir = join(tmpdir, "repo")

    def test_it(is_remote=False):
        conf = config.Config()

        conf.project = mirror_dir
        conf.repo = dvcs.path
        _test_generic_repo(conf, tmpdir, 'master~4..master', 'master', 'tag5',
                           is_remote=is_remote)

        conf.branches = ['master', 'some-branch']
        branch_commits = {
            'master': [dvcs.get_hash('master'), dvcs.get_hash('master~6')],
            'some-branch': [dvcs.get_hash('some-branch'), dvcs.get_hash('some-branch~6')]
        }
        _test_branches(conf, branch_commits)

    test_it()

    # local repo, so it should not not have cloned it
    assert not os.path.isdir(mirror_dir)

    # try again, pretending the repo is not local
    from asv.plugins.git import Git
    old_local_method = Git.is_local_repo
    old_url_match = Git.url_match
    try:
        Git.is_local_repo = classmethod(lambda cls, path:
                                        path != dvcs.path and
                                        old_local_method(path))
        Git.url_match = classmethod(lambda cls, url: os.path.isdir(url))
        test_it(is_remote=True)
        assert os.path.isdir(mirror_dir)
    finally:
        Git.is_local_repo = old_local_method
        Git.url_match = old_url_match


@pytest.mark.skipif(hglib is None,
                    reason="needs hglib")
def test_repo_hg(tmpdir):
    tmpdir = six.text_type(tmpdir)

    conf = config.Config()

    dvcs = tools.generate_test_repo(tmpdir, list(range(10)), dvcs_type='hg', 
                                    extra_branches=[('default~4', 'some-branch',[11, 12, 13])])

    mirror_dir = join(tmpdir, "repo")

    def test_it(is_remote=False):
        conf.project = mirror_dir
        conf.repo = dvcs.path
        _test_generic_repo(conf, tmpdir, hash_range="reverse(default~3::default)",
                           master="default", branch="tag5",
                           is_remote=is_remote)

        conf.branches = ['default', 'some-branch']
        branch_commits = {
            'default': [dvcs.get_hash('default'), dvcs.get_hash('default~6')],
            'some-branch': [dvcs.get_hash('some-branch'), dvcs.get_hash('some-branch~6')]
        }
        _test_branches(conf, branch_commits)

    test_it()

    # local repo, so it should not not have cloned it
    assert not os.path.isdir(mirror_dir)

    # try again, pretending the repo is not local
    from asv.plugins.mercurial import Hg
    old_local_method = Hg.is_local_repo
    old_url_match = Hg.url_match
    try:
        Hg.is_local_repo = classmethod(lambda cls, path:
                                       path != dvcs.path and
                                       old_local_method(path))
        Hg.url_match = classmethod(lambda cls, url: os.path.isdir(url))
        test_it(is_remote=True)
        assert os.path.isdir(mirror_dir)
    finally:
        Hg.is_local_repo = old_local_method
        Hg.url_match = old_url_match


@pytest.mark.parametrize("dvcs_type", [
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
def test_follow_first_parent(tmpdir, dvcs_type):
    """
    This test ensure we follow the first parent in case of merges

    The revision graph looks like this:

        o  Revision 5 (stable)
        |
        o    Merge default
        |\
        | o  Revision 4 (default)
        | |
        | o  Merge stable
        |/|
        | o  Revision 3
        | |
        o |  Revision 2
        |/
        o  Revision 1


    """
    tmpdir = six.text_type(tmpdir)
    if dvcs_type == "git":
        master = "master"
    elif dvcs_type == "hg":
        master = "default"
    dvcs = tools.make_test_repo(tmpdir, dvcs_type, [
        ("commit", 1),
        ("checkout", "stable", master),
        ("commit", 2),
        ("checkout", master),
        ("commit", 3),
        ("merge", "stable"),
        ("commit", 4),
        ("checkout", "stable"),
        ("merge", master),
        ("commit", 5),
        ("checkout", master),
    ])

    conf = config.Config()
    conf.branches = [master, "stable"]
    conf.repo = dvcs.path
    conf.project = join(tmpdir, "repo")
    r = repo.get_repo(conf)
    branch_cache = BranchCache(conf, r)
    expected = {
        master: set([
            "Revision 4",
            "Merge stable",
            "Revision 3",
            "Revision 1",
        ]),
        "stable": set([
            "Revision 5",
            "Merge {0}".format(master),
            "Revision 2",
            "Revision 1",
        ]),
    }
    for branch in conf.branches:
        commits = set([
            dvcs.get_commit_message(commit_hash)
            for commit_hash in branch_cache.get_branch_commits(branch)
        ])
        assert commits == expected[branch]
