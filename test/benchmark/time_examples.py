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


class TimeWithRepeat(object):
    # Check that setup is re-run on each repeat
    called = None
    number = 1
    repeat = 10
    count = 0

    def setup(self):
        assert self.called is None
        self.called = False

    def teardown(self):
        assert self.called is True
        self.called = None
        print("<%d>" % (self.count,))

    def time_it(self):
        assert self.called is False
        self.called = True
        self.count += 1


class TimeWithRepeatCalibrate(object):
    # Check that setup is re-run on each repeat, apart from
    # autodetection of suitable `number`
    repeat = 1
    number = 0
    goal_time = 0.1

    def setup(self):
        print("setup")

    def time_it(self):
        pass
