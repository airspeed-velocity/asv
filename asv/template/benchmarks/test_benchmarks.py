# Write the benchmarking functions here.  Each benchmark
# is in a class that inherits from unittest.TestCase.  It may
# have a `setUp` method, that isn't included in the timings.

import unittest


class TestIteration(unittest.TestCase):
    """
    An example benchmark that times the performance of various kinds
    of iterating over dictionaries in Python.
    """
    def setUp(self):
        self.d = {}
        for x in range(500):
            self.d[x] = None

    def test_keys(self):
        for key in self.d.keys():
            pass

    def test_iterkeys(self):
        for key in self.d.iterkeys():
            pass

    def test_range(self):
        d = self.d
        for key in range(500):
            x = d[key]

    def test_xrange(self):
        d = self.d
        for key in xrange(500):
            x = d[key]
