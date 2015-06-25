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

    def __init__(self, url, path, _checkout_copy=False):
        self._git = util.which("git")
        self._path = os.path.abspath(path)
        self._pulled = False

        if not os.path.isdir(self._path):
            args = ['clone']
            if _checkout_copy:
                args.append('--shared')
            else:
                log.info("Cloning project")
                args.append('--mirror')
            args.extend([url, self._path])
            self._run_git(args, chdir=False)

    @classmethod
    def url_match(cls, url):
        regexes = [
            '^https?://.*?\.git$',
            '^git@.*?\.git$']

        for regex in regexes:
            if re.match(regex, url):
                return True

        # Check for a local path
        if os.path.isdir(url) and os.path.isdir(os.path.join(url, '.git')):
            return True

        return False

    def _run_git(self, args, chdir=True, **kwargs):
        if chdir:
            cwd = self._path
        else:
            cwd = None
        kwargs['cwd'] = cwd
        return util.check_output(
            [self._git] + args, **kwargs)

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

    def pull(self):
        # We assume the remote isn't updated during the run of asv
        # itself.
        if self._pulled is True:
            return

        log.info("Fetching recent changes")
        self._run_git(['fetch', 'origin'])
        self._pulled = True

    def checkout(self, path, commit_hash):
        subrepo = Git(self._path, path, _checkout_copy=True)
        subrepo._run_git(['checkout', '-f', commit_hash])
        subrepo.clean()

    def clean(self):
        self._run_git(['clean', '-fxd'])

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
