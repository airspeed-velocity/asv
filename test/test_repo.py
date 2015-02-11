# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import pytest

from asv import config
from asv import repo

try:
    import hglib
except ImportError:
    hglib = None

def _test_generic_repo(conf,
                       hash_range="ae0c27b65741..e6f382a704f7",
                       master="master",
                       branch="gh-pages"):

    r = repo.get_repo(conf)
    r.checkout(master)
    r.checkout(branch)
    r.checkout(master)

    hashes = r.get_hashes_from_range(hash_range)
    assert len(hashes) == 4

    dates = [r.get_date(hash) for hash in hashes]
    assert dates == sorted(dates)[::-1]

    tags = r.get_tags()
    for tag in tags:
        r.get_date_from_tag(tag)


def test_repo_git(tmpdir):
    conf = config.Config()

    conf.project = six.text_type(tmpdir.join("repo"))
    conf.repo = "https://github.com/spacetelescope/asv.git"
    _test_generic_repo(conf)


@pytest.mark.xfail(hglib is None,
                   reason="needs hglib")
def test_repo_hg(tmpdir):
    conf = config.Config()

    conf.project = six.text_type(tmpdir.join("repo"))
    conf.repo = "hg+https://bitbucket.org/nds-org/nds-labs"
    _test_generic_repo(conf, hash_range="a8ca24ac6b77:9dc758deba8",
                       master="tip", branch="dev")
