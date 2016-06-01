# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Supports mercurial repositories for the benchmarked project.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import re
try:
    import hglib
except ImportError as exc:
    hglib = None

from ..console import log
from ..repo import Repo
from .. import util


class Hg(Repo):
    dvcs = "hg"
    _default_branch = "default"

    def __init__(self, url, mirror_path):
        # TODO: shared repositories in Mercurial are only possible
        # through an extension, and it's not clear how to use those in
        # this context.  So here, we always make full clones for
        # each of the environments.

        self._path = os.path.abspath(mirror_path)
        self._pulled = False
        if hglib is None:
            raise ImportError("hglib")

        if self.is_local_repo(url):
            # Local repository, no need for mirror
            self._path = os.path.abspath(url)
            self._pulled = True
        elif not self.is_local_repo(self._path):
            if os.path.exists(self._path):
                self._raise_bad_mirror_error(self._path)

            # Clone is missing
            log.info("Cloning project")
            if url.startswith("hg+"):
                url = url[3:]

            # Mercurial branches are global, so there is no need for
            # an analog of git --mirror
            hglib.clone(url, dest=self._path, noupdate=True)

        self._repo = hglib.open(self._path)

    @classmethod
    def is_local_repo(cls, path):
        return (os.path.isdir(path) and
                os.path.isdir(os.path.join(path, '.hg')))

    @classmethod
    def url_match(cls, url):
        regexes = [
            '^hg\+https?://.*$',
            '^https?://.*?\.hg$',
            '^ssh://hg@.*$']

        for regex in regexes:
            if re.match(regex, url):
                return True

        # Check for a local path
        if cls.is_local_repo(url):
            return True

        return False

    def get_range_spec(self, commit_a, commit_b):
        return '{0}::{1} and not {0}'.format(commit_a, commit_b, commit_a)

    def get_new_range_spec(self, latest_result, branch=None):
        return '{0}::{1}'.format(latest_result, self.get_branch_name(branch))

    def pull(self):
        # We assume the remote isn't updated during the run of asv
        # itself.
        if self._pulled:
            return

        log.info("Fetching recent changes")
        self._repo.pull()
        self._pulled = True

    def checkout(self, path, commit_hash):
        # Need to pull -- the copy is not updated automatically, since
        # the repository data is not shared

        def checkout_existing():
            with hglib.open(path) as subrepo:
                subrepo.pull()
                subrepo.update(commit_hash, clean=True)
                subrepo.rawcommand(["--config", "extensions.purge=",
                                    "purge", "--all"])

        if os.path.isdir(path):
            try:
                checkout_existing()
            except (hglib.error.CommandError, hglib.error.ServerError):
                # Remove and re-clone
                util.long_path_rmtree(path)

        if not os.path.isdir(path):
            hglib.clone(self._path, dest=path)
            checkout_existing()

    def get_date(self, hash):
        # TODO: This works on Linux, but should be extended for other platforms
        rev = self._repo.log(hash)[0]
        return int(rev.date.strftime("%s")) * 1000

    def get_hashes_from_range(self, range_spec):
        range_spec = "sort({0}, -rev)".format(range_spec)
        return [rev.node for rev in self._repo.log(range_spec,
                                                   followfirst=True)]

    def get_hash_from_name(self, name):
        if name is None:
            name = self.get_branch_name()
        return self._repo.log(name)[0].node

    def get_hash_from_parent(self, name):
        return self.get_hash_from_name('p1({0})'.format(name))

    def get_tags(self):
        tags = {}
        for item in self._repo.log("tag()"):
            tags[item.tags] = item.node
        return tags

    def get_date_from_name(self, name):
        return self.get_date(name)

    def get_branch_commits(self, branch):
        return self.get_hashes_from_range("ancestors({0})".format(self.get_branch_name(branch)))

    def get_revisions(self, commits):
        revisions = {}
        for i, item in enumerate(self._repo.log("all()")):
            if item.node in commits:
                revisions[item.node] = i
        return revisions
