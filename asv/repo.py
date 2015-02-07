# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


from . import util


class Repo(object):
    """
    Base class for repository handlers.
    """
    def __init__(self, url, path, shared=False):
        """
        Parameters
        ----------
        url : str
            The URL to the repository to clone

        path : str
            The local path to clone into

        shared : bool, optional.
            When `True`, share the repository history with the source
            repo's history.
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

    def get_hash_from_tag(self, range):
        """
        Get a hash from a given tag, branch or hash.  The acceptable
        syntax will depend on the DVCS used.
        """
        raise NotImplementedError()

    def get_hash_from_head(self):
        """
        Get the hash of the currently checked-out commit.
        """
        raise NotImplementedError()

    def get_tags(self):
        """
        Get a list of all of the tags defined in the repo.
        """
        raise NotImplementedError()

    def get_date_from_tag(self, tag):
        """
        Get a Javascript timestamp for a particular tag.
        """
        raise NotImplementedError()

    def checkout_remote_branch(self, remote, branch):
        """
        Fetch and then checkout a remote branch.
        """
        raise NotImplementedError()

    def checkout_parent(self):
        """
        Checkout the parent of the currently checked out commit.
        """
        raise NotImplementedError()


class NoRepository(Repo):
    """
    Project installed in the current environment
    """

    dvcs = "none"

    def __init__(self, url=None, path=None, shared=False):
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

    def checkout(self, branch):
        self._check_branch(branch)

    def clean(self, branch):
        self._check_branch(branch)

    def get_date(self, hash):
        self._raise_error()

    def get_hashes_from_range(self, range):
        return [None]

    def get_hash_from_head(self):
        return None

    def get_hash_from_tag(self, range):
        return None

    def get_tags(self):
        return []

    def get_date_from_tag(self, tag):
        self._raise_error()

    def checkout_remote_branch(self, remote, branch):
        self._raise_error()

    def checkout_parent(self):
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
