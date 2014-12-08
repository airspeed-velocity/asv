# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ..repo import Repo


class DumbRepo(Repo):
    """
    A dumb "repository" that doesn't actually do anything (for running
    with the current Python).
    """
    def __init__(self, *args):
        pass

    @property
    def path(self):
        return "<dumb>"

    @classmethod
    def url_match(cls, url):
        # This repository class is never selected implicitly.
        return False

    def checkout(self, branch='master'):
        pass
