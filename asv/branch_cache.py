# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import tempfile
import six

from . import util


class BranchCache(object):
    def __init__(self, conf, repo):
        self._branches = conf.branches
        self._repo = repo
        if not self._branches:
            # Master branch only
            self._branches = [None]
        self._hashes = None

    def _load(self):
        if self._hashes is not None:
            return
        self._hashes = {}
        for branch in self._branches:
            spec = self._repo.get_branch_range_spec(branch)
            hashes = set(self._repo.get_hashes_from_range(spec))
            self._hashes[spec] = (branch, hashes)

    def get_branches(self, commit_hash):
        self._load()
        branches = []
        for spec, item in six.iteritems(self._hashes):
            branch, hashes = item
            if commit_hash in hashes:
                branches.append(branch)
        return branches

    def get_branch_commits(self, branch):
        self._load()
        spec = self._repo.get_branch_range_spec(branch)
        return self._hashes[spec][1]
