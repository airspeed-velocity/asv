# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


import os
import re

from .console import console
from . import util


class Repo(object):
    """
    Base class for repository handlers.
    """
    def __init__(self, url, path):
        """
        Parameters
        ----------
        url : str
            The URL to the repository to clone

        path : str
            The local path to clone into
        """
        raise NotImplementedError()

    @classmethod
    def url_match(cls, url):
        """
        Returns `True` if the url is of the right type for this kind
        of repository.
        """
        raise NotImplementedError()

    def checkout(self, branch):
        """
        Checkout a given branch or commit hash.  Also cleans the
        checkout of any non-source-controlled files.
        """
        raise NotImplementedError()

    def clean(self):
        """
        Clean the repository of any non-checked-in files.
        """
        raise NotImplementedError()

    def get_date(self, hash):
        """
        Get a Javascript timestamp for a particular commit.
        """
        raise NotImplementedError()

    def get_hashes_from_range(self, range):
        """
        Get a list of commit hashes given a range specifier.  The
        syntax of the range specifier will depend on the DVCS used.
        """
        raise NotImplementedError()

    def get_tags(self):
        """
        Get a list of all of the tags defined in the repo.
        """
        raise NotImplementedError()

    def get_date_from_tag(self, tag):
        """
        Get a Javascript timestamp for a particular tag
        """
        raise NotImplementedError()


class Git(Repo):
    def __init__(self, url, path):
        self._git = util.which("git")

        self._path = os.path.abspath(path)
        if not os.path.exists(self._path):
            console.message("Cloning project", "green")
            self._run_git(['clone', url, self._path], chdir=False)

        console.message("Fetching recent changes", "green")
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
            ['log', '--quiet', '--format=format:%H', range_spec], dots=False
        ).strip().split()

    def get_tags(self):
        return self._run_git(
            ['tag', '-l']).strip().split()

    def get_date_from_tag(self, tag):
        return self.get_date(tag + "^{commit}")


def get_repo(url, path):
    classes = [Git]

    for cls in classes:
        if cls.url_match(url):
            return cls(url, path)

    raise ValueError(
        "Can not determine what kind of DVCS to use for URL '{0}'".format(url))
