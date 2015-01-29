# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


def track_param(n):
    return 42

track_param.params = [10, 20]


def mem_param(n, m):
    return [[0]*m]*n

mem_param.params = ([10, 20], [2, 3])
mem_param.param_names = ['number', 'depth']


class ParamSuite:
    params = ['a', 'b', 'c']

    def setup(self):
        self.values = {'a': 1, 'b': 2, 'c': 3}
        self.count = 0

    def setup_param(self, p):
        self.value = self.values[p]

    def track_value(self, p):
        return self.value + self.count

    def teardown_param(self, p):
        self.count += 1
        del self.value

    def teardown(self):
        del self.values
