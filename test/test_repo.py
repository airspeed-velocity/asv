# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

from asv import repo


def test_repo(tmpdir):
    path = six.text_type(tmpdir.join("repo"))
    url = "https://github.com/spacetelescope/asv.git"

    r = repo.get_repo(url, path)
    r.checkout("master")
    r.checkout("gh-pages")
    r.checkout("master")

    hashes = r.get_hashes_from_range("ae0c27b65741..e6f382a704f7")
    assert len(hashes) == 4

    dates = [r.get_date(hash) for hash in hashes]
    assert dates == sorted(dates)[::-1]

    tags = r.get_tags()
    for tag in tags:
        r.get_date_from_tag(tag)
