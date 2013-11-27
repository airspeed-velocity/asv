# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import unittest

import sys
if sys.version_info[0] == 3:
    xrange = range


class TestSuite1(unittest.TestCase):
    def test_example_benchmark_1(self):
        s = ''
        for i in xrange(100):
            s = s + 'x'

    def test_example_benchmark_2(self):
        s = []
        for i in xrange(100):
            s.append('x')
        ''.join(s)
