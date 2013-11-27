# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import unittest

import sys
if sys.version_info[0] == 3:
    xrange = range


class TestSecondary(unittest.TestCase):
    def test_factorial(self):
        x = 1
        for i in xrange(100):
            x *= i

    def test_exception(self):
        raise RuntimeError()
