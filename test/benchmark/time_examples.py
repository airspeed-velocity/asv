# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
if sys.version_info[0] == 3:
    xrange = range


class TimeSuite:
    def setup(self):
        self.n = 100

    def time_example_benchmark_1(self):
        s = ''
        for i in xrange(self.n):
            s = s + 'x'

    def time_example_benchmark_2(self):
        s = []
        for i in xrange(self.n):
            s.append('x')
        ''.join(s)


class TimeSuiteSub(TimeSuite):
    pass
