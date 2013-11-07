# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import datetime
import os

from .console import console
from . import util


class Repo(object):
    def __init__(self, url, path):
        self.git = util.which("git")[0]

        self.path = path
        if not os.path.exists(self.path):
            console.message("Cloning project", "green")
            self._run_git(['clone', url, self.path], chdir=False)

        console.message("Fetching recent changes", "green")
        self._run_git(['fetch', 'origin'])
        self.checkout('origin/master')

    def _run_git(self, args, chdir=True):
        if chdir:
            orig_dir = os.getcwd()
            os.chdir(self.path)
        try:
            return util.check_output(
                [self.git] + args)
        finally:
            if chdir:
                os.chdir(orig_dir)

    def checkout(self, branch):
        self._run_git(['checkout', branch])

    def clean(self):
        self._run_git(['clean', '-fxd'])

    def get_branches(self, spec, steps=None):
        if '..' in spec:
            start, end = spec.split('..')

    def get_date(self, hash):
        return int(self._run_git(
            ['show', hash, '--quiet', '--format=format:%at']).strip())

    def get_hashes_from_range(self, range):
        return self._run_git(
            ['log', '--quiet', '--format=format:%H', range]
        ).strip().split()
