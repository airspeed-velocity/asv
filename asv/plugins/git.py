# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Supports git repositories for the benchmarked project.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import re

from ..console import log
from ..repo import Repo
from .. import util


class Git(Repo):
    dvcs = "git"

    def __init__(self, url, mirror_path):
        self._git = util.which("git")
        self._path = os.path.abspath(mirror_path)
        self._pulled = False

        if self.is_local_repo(url):
            # Local repository, no need for mirror
            self._path = os.path.abspath(url)
            self._pulled = True
        elif not os.path.isdir(self._path):
            # Clone is missing
            log.info("Cloning project")
            self._run_git(['clone', '--mirror', url, self._path],
                           cwd=None)

    @classmethod
    def is_local_repo(cls, path):
        return os.path.isdir(path) and (
            os.path.isdir(os.path.join(path, '.git')) or
            os.path.isdir(os.path.join(path, 'objects')))

    @classmethod
    def url_match(cls, url):
        regexes = [
            '^https?://.*?\.git$',
            '^git@.*?\.git$']

        for regex in regexes:
            if re.match(regex, url):
                return True

        # Check for a local path
        if cls.is_local_repo(url):
            return True

        return False

    def _run_git(self, args, cwd=True, **kwargs):
        if cwd is True:
            cwd = self._path
        kwargs['cwd'] = cwd
        return util.check_output([self._git] + args, **kwargs)

    def get_new_range_spec(self, latest_result, branch=None):
        if branch is None:
            return '{0}..master'.format(latest_result)
        else:
            return '{0}..{1}'.format(latest_result, branch)

    def get_branch_range_spec(self, branch):
        if branch is None:
            return 'master'
        else:
            return branch

    def get_range_spec(self, commit_a, commit_b):
        return '{0}..{1}'.format(commit_a, commit_b)

    def pull(self):
        # We assume the remote isn't updated during the run of asv
        # itself.
        if self._pulled:
            return

        log.info("Fetching recent changes")
        self._run_git(['fetch', 'origin'])
        self._pulled = True

    def checkout(self, path, commit_hash):
        if not os.path.isdir(path):
            self._run_git(['clone', '--shared', self._path, path],
                          cwd=None)

        self._run_git(['checkout', '-f', commit_hash], cwd=path)
        self._run_git(['clean', '-fdx'], cwd=path)

    def get_date(self, hash):
        # TODO: This works on Linux, but should be extended for other platforms
        return int(self._run_git(
            ['show', hash, '--quiet', '--format=format:%at'],
            valid_return_codes=(0, 1), dots=False).strip().split()[-1]) * 1000

    def get_hashes_from_range(self, range_spec):
        args = ['log', '--quiet', '--first-parent', '--format=format:%H']
        if range_spec != "":
            args += range_spec.split()
        output = self._run_git(args, valid_return_codes=(0, 1), dots=False)
        return output.strip().split()

    def get_hash_from_name(self, name):
        return self._run_git(['rev-parse', name],
                             dots=False).strip().split()[0]

    def get_hash_from_master(self):
        return self.get_hash_from_name('master')

    def get_hash_from_parent(self, name):
        return self.get_hash_from_name(name + '^')

    def get_tags(self):
        return self._run_git(
            ['tag', '-l']).strip().split()

    def get_date_from_name(self, name):
        return self.get_date(name + "^{commit}")
