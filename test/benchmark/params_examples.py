# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function)

import os

class ClassOne(object):
    pass

class ClassTwo(object):
    pass


def track_param(n):
    return 42

track_param.params = [ClassOne, ClassTwo]


def mem_param(n, m):
    return [[0]*m]*n

mem_param.params = ([10, 20], [2, 3])
mem_param.param_names = ['number', 'depth']


class ParamSuite:
    params = ['a', 'b', 'c']

    def setup(self, p):
        values = {'a': 1, 'b': 2, 'c': 3}
        self.count = 0
        self.value = values[p]

    def track_value(self, p):
        return self.value + self.count

    def teardown(self, p):
        self.count += 1
        del self.value


class TuningTest:
    params = [1, 2]
    counter = [0]
    number = 10
    repeat = 10

    def setup(self, n):
        self.number = 1
        self.repeat = n
        self.counter[0] = 0

    def time_it(self, n):
        self.counter[0] += 1

    def teardown(self, n):
        # The time benchmark may call it one additional time
        if not (n <= self.counter[0] <= n + 1):
            raise RuntimeError("Number and repeat didn't have effect")


def setup_skip(n):
    if n > 2000:
        raise NotImplementedError()


def time_skip(n):
    list(range(n))
time_skip.params = [1000, 2000, 3000]
time_skip.setup = setup_skip
time_skip.goal_time = 0.01


def track_find_test(n):
    import asv_test_repo

    return asv_test_repo.dummy_value[n - 1]

track_find_test.params = [1, 2]
