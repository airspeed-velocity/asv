# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


from . import util


class Repo(object):
    """
    Base class for repository handlers.
    """
    def __init__(self, url, path):
        """
        Create a mirror of the repository at `url`, without a working tree.

        Parameters
        ----------
        url : str
            The URL to the repository to clone

        path : str
            The local path to clone into
        """
        raise NotImplementedError()

    def checkout(self, path, commit_hash):
        """
        Check out a clean working tree from the current repository
        to the given path

        Parameters
        ----------
        path : str
            The local path to check out into
        commit_hash : str
            The commit hash to check out

        """
        raise NotImplementedError()

    @classmethod
    def url_match(cls, url):
        """
        Returns `True` if the url is of the right type for this kind
        of repository.
        """
        raise NotImplementedError()

    def get_range_spec(self, commit_a, commit_b):
        """
        Returns a formatted string giving the results between
        commit_a (exclusive) and commit_b (inclusive).
        """
        raise NotImplementedError()

    def get_new_range_spec(self, latest_result, branch=None):
        """
        Returns a formatted string giving the results between the 
        latest result and the newest hash in a given branch.
        If no branch given, use the 'master' branch.
        """
        raise NotImplementedError()

    def get_branch_range_spec(self, branch):
        """
        Returns a formatted string giving the results in a given branch.
        If branch is None, use the 'master' branch.
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

    def get_hash_from_name(self, name):
        """
        Get a hash from a given tag, branch or hash.  The acceptable
        syntax will depend on the DVCS used.
        """
        raise NotImplementedError()

    def get_hash_from_master(self):
        """
        Get the hash of the current master branch commit.
        """
        raise NotImplementedError()

    def get_hash_from_parent(self, name):
        """
        Checkout the parent of the currently checked out commit.
        """
        raise NotImplementedError()

    def get_tags(self):
        """
        Get a list of all of the tags defined in the repo.
        """
        raise NotImplementedError()

    def get_date_from_name(self, name):
        """
        Get a Javascript timestamp for a particular name.
        """
        raise NotImplementedError()


class NoRepository(Repo):
    """
    Project installed in the current environment
    """

    dvcs = "none"

    def __init__(self, url=None, path=None):
        self.url = None
        self.path = None

    def _raise_error(self):
        raise ValueError("Using the currently installed project version: "
                         "operations requiring repository are not possible")

    def _check_branch(self, branch):
        if branch is not None:
            self._raise_error()

    @classmethod
    def url_match(cls, url):
        return False

    def checkout(self, path, commit_hash):
        self._check_branch(commit_hash)

    def clean(self):
        return

    def get_date(self, hash):
        self._raise_error()

    def get_hashes_from_range(self, range):
        return [None]

    def get_hash_from_master(self):
        return None

    def get_hash_from_name(self, name):
        return None

    def get_hash_from_parent(self, name):
        self._raise_error()

    def get_tags(self):
        return []

    def get_date_from_name(self, name):
        self._raise_error()


def get_repo(conf):
    """
    Get a Repo subclass for the given configuration.

    If the configuration does not explicitly specify a repository
    type, it will attempt to automatically determine one from the
    ``conf.repo`` URL.
    """
    if conf.repo is None:
        return None

    if conf.dvcs is not None:
        for cls in util.iter_subclasses(Repo):
            if getattr(cls, 'dvcs') == conf.dvcs:
                return cls(conf.repo, conf.project)
    else:
        for cls in util.iter_subclasses(Repo):
            if cls.url_match(conf.repo):
                return cls(conf.repo, conf.project)

    raise util.UserError(
        "Can not determine what kind of DVCS to use for URL '{0}'".format(conf.repo))
