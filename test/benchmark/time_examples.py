# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
if sys.version_info[0] == 3:
    xrange = range

import warnings


class TimeSuite:
    goal_time = 0.1

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


def time_with_warnings():
    print('hi')
    warnings.warn('before')
    1 / 0
    warnings.warn('after')

time_with_warnings.goal_time = 0.1


def time_with_timeout():
    while True:
        pass

time_with_timeout.timeout = 0.1
