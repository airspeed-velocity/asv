# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import join

import six
import pytest

from asv import config
from asv import repo

try:
    import hglib
except ImportError:
    hglib = None

from . import tools


def _test_generic_repo(conf, tmpdir, hash_range, master, branch):
    workcopy_dir = join(tmpdir, "workcopy")

    r = repo.get_repo(conf)

    r.checkout(workcopy_dir, master)
    r.checkout(workcopy_dir, branch)
    r.checkout(workcopy_dir, master)

    hashes = r.get_hashes_from_range(hash_range)
    assert len(hashes) == 4

    dates = [r.get_date(hash) for hash in hashes]
    assert dates == sorted(dates)[::-1]

    tags = r.get_tags()
    for tag in tags:
        r.get_date_from_name(tag)


def test_repo_git(tmpdir):
    tmpdir = six.text_type(tmpdir)

    conf = config.Config()

    conf.project = join(tmpdir, "repo")
    conf.repo = tools.generate_test_repo(tmpdir, list(range(10)))
    _test_generic_repo(conf, tmpdir, 'master~4..master', 'master', 'tag5')


@pytest.mark.xfail(hglib is None,
                   reason="needs hglib")
def test_repo_hg(tmpdir):
    tmpdir = six.text_type(tmpdir)

    conf = config.Config()

    conf.project = join(tmpdir, "repo")
    conf.repo = tools.generate_test_repo(tmpdir, list(range(10)),
                                             dvcs_type='hg')
    _test_generic_repo(conf, tmpdir, hash_range="tip:-4",
                       master="tip", branch="tag5")
