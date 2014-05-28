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
    def __init__(self, url, path):
        self._git = util.which("git")
        self._path = os.path.abspath(path)

        if not os.path.exists(self._path):
            log.info("Cloning project")
            self._run_git(['clone', url, self._path], chdir=False)

        log.info("Fetching recent changes")
        self.pull()

    @property
    def path(self):
        return self._path

    @classmethod
    def url_match(cls, url):
        regexes = [
            '^https?://.*?\.git$',
            '^git@.*?\.git$']

        for regex in regexes:
            if re.match(regex, url):
                return True
        return False

    def _run_git(self, args, chdir=True, **kwargs):
        if chdir:
            orig_dir = os.getcwd()
            os.chdir(self._path)
        try:
            return util.check_output(
                [self._git] + args, **kwargs)
        finally:
            if chdir:
                os.chdir(orig_dir)

    def pull(self):
        self._run_git(['fetch', 'origin'])
        self.checkout('master')
        self._run_git(['pull'])

    def checkout(self, branch='master'):
        self._run_git(['checkout', branch])
        self.clean()

    def clean(self):
        self._run_git(['clean', '-fxd'])

    def get_date(self, hash):
        # TODO: This works on Linux, but should be extended for other platforms
        return int(self._run_git(
            ['show', hash, '--quiet', '--format=format:%ct'],
            dots=False).strip().split()[0]) * 1000

    def get_hashes_from_range(self, range_spec):
        if range_spec == 'master':
            range_spec = 'master^!'
        return self._run_git(
            ['log', '--quiet', '--first-parent', '--format=format:%H',
             range_spec], dots=False
        ).strip().split()

    def get_hash_from_tag(self, tag):
        return self._run_git(
            ['show', tag, '--quiet', '--format=format:%H'],
            dots=False).strip().split()[0]

    def get_tags(self):
        return self._run_git(
            ['tag', '-l']).strip().split()

    def get_date_from_tag(self, tag):
        return self.get_date(tag + "^{commit}")
