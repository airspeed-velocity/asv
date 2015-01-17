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

    def get_new_range_spec(self, latest_result):
        """
        Returns a formatted string giving the results between the 
        latest result and the newest hash.
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


def get_repo(conf):
    """
    Get a Repo subclass for the given configuration.

    If the configuration does not explicitly specify a repository
    type, it will attempt to automatically determine one from the
    ``conf.repo`` URL.
    """
    for cls in util.iter_subclasses(Repo):
        if cls.url_match(conf.repo):
            return cls(conf.repo, conf.project)

    raise util.UserError(
        "Can not determine what kind of DVCS to use for URL '{0}'".format(conf.repo))
