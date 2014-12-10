# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
if sys.version_info[0] == 3:
    xrange = range


from .shared import shared_function


class TimeSecondary:
    def time_factorial(self):
        x = 1
        for i in xrange(100):
            x *= i
        # This is to generate invalid output
        sys.stdout.write("X")

    def time_exception(self):
        raise RuntimeError()


def track_value():
    return 42.0


def test_shared_code():
    assert shared_function() == 42
