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
    track_file = os.environ.get('_ASV_TEST_TRACK_FILE')
    if track_file is None:
        return 42

    if not os.path.isfile(track_file):
        count = 0
    else:
        with open(track_file, 'r') as f:
            text = f.read()
        count = int(text)

    # Values simulating regression after the first commit (assumes
    # knowledge on how asv find evaluates the first three commits)
    values = {
        # lo
        0: (3, 6),

        # mid
        1: (6, None),

        # hi
        2: (6, 1),

        # some of the rest
        3: (None, 1),
        4: (6, None),
    }


    if count in values:
        value = values[count][n-1]
    else:
        if n == 1:
            value = 6
        else:
            value = 1

    if n == 2:
        count += 1

    with open(track_file, 'w') as f:
        f.write(str(count))

    return value

track_find_test.params = [1, 2]
