# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import dirname, join

from asv import config


def test_config():
    conf = config.Config.load(join(dirname(__file__), 'asv.conf.json'))

    assert conf.project == 'astropy'
    assert conf.matrix == {
        "numpy": ["1.8"],
        "Cython": []
    }
