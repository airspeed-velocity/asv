# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import re
import pytest

from asv import util

from . import tools

from .test_dev import basic_conf


def test_check(capsys, basic_conf):
    tmpdir, local, conf = basic_conf

    # Test check runs (with full benchmark suite)
    with pytest.raises(util.UserError, message="Benchmark suite check failed."):
        tools.run_asv_with_conf(conf, 'check', "--python=same")

    text, err = capsys.readouterr()

    assert re.search(r"cache_examples\.[A-Za-z]+\.track_[a-z]+: call: wrong number of arguments", text)
    assert text.count("wrong number of arguments") == 1
