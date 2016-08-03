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

from asv import config
from asv import repo
from asv import util

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

    # Subrepo creation
    r.checkout(workcopy_dir, master)
    assert os.path.exists(join(workcopy_dir, "setup.py"))

    for filename in ("README", "untracked"):
        with open(join(workcopy_dir, filename), "wb") as fd:
            fd.write(b"foo")

    # After checkout the subrepo has been cleaned
    r.checkout(workcopy_dir, branch)
    assert not os.path.exists(join(workcopy_dir, "untracked"))
    with open(join(workcopy_dir, "README"), "rb") as fd:
        data = fd.read(33)
        assert data == b"This is the asv_test_repo project"

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

    assert len(conf.branches) == 2

    for branch in conf.branches:
        commits = r.get_branch_commits(branch)

        for commit in branch_commits[branch]:
            assert commit in commits


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


def test_repo_git_annotated_tag_date(tmpdir):
    tmpdir = six.text_type(tmpdir)

    dvcs = tools.generate_test_repo(tmpdir, list(range(5)), dvcs_type='git')

    conf = config.Config()
    conf.project = 'sometest'
    conf.repo = dvcs.path

    r = repo.get_repo(conf)
    d1 = r.get_date('tag1')
    d2 = r.get_date(r.get_hash_from_name('tag1'))
    assert d1 == d2


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


@pytest.fixture(params=[
    "git",
    pytest.mark.skipif(hglib is None, reason="needs hglib")("hg"),
])
def two_branch_repo_case(request, tmpdir):
    """
    This test ensure we follow the first parent in case of merges

    The revision graph looks like this:

        @  Revision 6 (default)
        |
        | o  Revision 5 (stable)
        | |
        | o  Merge master
        |/|
        o |  Revision 4
        | |
        o |  Merge stable
        |\|
        o |  Revision 3
        | |
        | o  Revision 2
        |/
        o  Revision 1

    """
    dvcs_type = request.param
    tmpdir = six.text_type(tmpdir)
    if dvcs_type == "git":
        master = "master"
    elif dvcs_type == "hg":
        master = "default"
    dvcs = tools.generate_repo_from_ops(tmpdir, dvcs_type, [
        ("commit", 1),
        ("checkout", "stable", master),
        ("commit", 2),
        ("checkout", master),
        ("commit", 3),
        ("merge", "stable"),
        ("commit", 4),
        ("checkout", "stable"),
        ("merge", master, "Merge master"),
        ("commit", 5),
        ("checkout", master),
        ("commit", 6),
    ])

    conf = config.Config()
    conf.branches = [master, "stable"]
    conf.repo = dvcs.path
    conf.project = join(tmpdir, "repo")
    r = repo.get_repo(conf)
    return dvcs, master, r, conf


def test_get_branch_commits(two_branch_repo_case):
    # Test that get_branch_commits() return an ordered list of commits (last
    # first) and follow first parent in case of merge
    dvcs, master, r, conf = two_branch_repo_case
    expected = {
        master: [
            "Revision 6",
            "Revision 4",
            "Merge stable",
            "Revision 3",
            "Revision 1",
        ],
        "stable": [
            "Revision 5",
            "Merge master",
            "Revision 2",
            "Revision 1",
        ],
    }
    for branch in conf.branches:
        commits = [
            dvcs.get_commit_message(commit_hash)
            for commit_hash in r.get_branch_commits(branch)
        ]
        assert commits == expected[branch]


@pytest.mark.parametrize("existing, expected", [
    # No existing commit, we expect all commits in commit order,
    # master branch first
    ([], ["Revision 6", "Revision 4", "Merge stable", "Revision 3",
          "Revision 1", "Revision 5", "Merge master", "Revision 2"]),

    # New commits on each branch
    (["Revision 4", "Merge master"], ["Revision 6", "Revision 5"]),

    # No new commits
    (["Revision 6", "Revision 5"], []),

    # Missing all commits on one branch (case of new branch added in config)
    (["Revision 6"], ["Revision 5", "Merge master", "Revision 2", "Revision 1"]),
], ids=["all", "new", "no-new", "new-branch-added-in-config"])
def test_get_new_branch_commits(two_branch_repo_case, existing, expected):
    dvcs, master, r, conf = two_branch_repo_case

    existing_commits = set()
    for branch in conf.branches:
        for commit in r.get_branch_commits(branch):
            message = dvcs.get_commit_message(commit)
            if message in existing:
                existing_commits.add(commit)

    assert len(existing_commits) == len(existing)

    new_commits = r.get_new_branch_commits(conf.branches, existing_commits)
    commits = [dvcs.get_commit_message(commit) for commit in new_commits]
    assert commits == expected


def test_git_submodule(tmpdir):
    tmpdir = six.text_type(tmpdir)

    # State 0 (no submodule)
    dvcs = tools.generate_test_repo(tmpdir, values=[0], dvcs_type='git')
    sub_dvcs = tools.generate_test_repo(tmpdir, values=[0], dvcs_type='git')
    ssub_dvcs = tools.generate_test_repo(tmpdir, values=[0], dvcs_type='git')
    commit_hash_0 = dvcs.get_hash("master")

    # State 1 (one submodule)
    dvcs.run_git(['submodule', 'add', sub_dvcs.path, 'sub1'])
    dvcs.commit('Add sub1')
    commit_hash_1 = dvcs.get_hash("master")

    # State 2 (one submodule with sub-submodule)
    dvcs.run_git(['submodule', 'update', '--init'])
    sub1_dvcs = tools.Git(join(dvcs.path, 'sub1'))
    sub_dvcs.run_git(['submodule', 'add', ssub_dvcs.path, 'ssub1'])
    sub_dvcs.commit('Add sub1')
    sub1_dvcs.run_git(['pull'])
    dvcs.run_git(['add', 'sub1'])
    dvcs.commit('Update sub1')
    sub1_hash_2 = sub1_dvcs.get_hash("master")
    commit_hash_2 = dvcs.get_hash("master")

    # State 3 (one submodule; sub-submodule removed)
    sub_dvcs.run_git(['rm', '-f', 'ssub1'])
    sub_dvcs.commit('Remove ssub1')
    sub1_dvcs.run_git(['pull'])
    dvcs.run_git(['add', 'sub1'])
    dvcs.commit('Update sub1 again')
    commit_hash_3 = dvcs.get_hash("master")

    # State 4 (back to one submodule with sub-submodule)
    sub1_dvcs.run_git(['checkout', sub1_hash_2])
    dvcs.run_git(['add', 'sub1'])
    dvcs.commit('Update sub1 3rd time')
    commit_hash_4 = dvcs.get_hash("master")

    # State 5 (remove final submodule)
    dvcs.run_git(['rm', '-f', 'sub1'])
    dvcs.commit('Remove sub1')
    commit_hash_5 = dvcs.get_hash("master")


    # Verify clean operation
    conf = config.Config()
    conf.branches = [None]
    conf.repo = dvcs.path
    conf.project = join(tmpdir, "repo")
    r = repo.get_repo(conf)

    checkout_dir = join(tmpdir, "checkout")

    # State 0
    r.checkout(checkout_dir, commit_hash_0)
    assert os.path.isfile(join(checkout_dir, 'README'))
    assert not os.path.exists(join(checkout_dir, 'sub1'))

    # State 1
    r.checkout(checkout_dir, commit_hash_1)
    assert os.path.isfile(join(checkout_dir, 'sub1', 'README'))
    assert not os.path.exists(join(checkout_dir, 'sub1', 'ssub1'))

    # State 2
    r.checkout(checkout_dir, commit_hash_2)
    assert os.path.isfile(join(checkout_dir, 'sub1', 'ssub1', 'README'))

    # State 3
    r.checkout(checkout_dir, commit_hash_3)
    assert os.path.isfile(join(checkout_dir, 'sub1', 'README'))
    assert not os.path.exists(join(checkout_dir, 'sub1', 'ssub1'))

    # State 4
    r.checkout(checkout_dir, commit_hash_4)
    assert os.path.isfile(join(checkout_dir, 'sub1', 'ssub1', 'README'))

    # State 4 (check clean -fdx runs in sub-sub modules)
    garbage_filename = join(checkout_dir, 'sub1', 'ssub1', '.garbage')
    util.write_json(garbage_filename, {})
    assert os.path.isfile(garbage_filename)
    r.checkout(checkout_dir, commit_hash_4)
    assert not os.path.isfile(garbage_filename)

    # State 5
    r.checkout(checkout_dir, commit_hash_5)
    assert os.path.isfile(join(checkout_dir, 'README'))
    assert not os.path.isdir(join(checkout_dir, 'sub1'))
