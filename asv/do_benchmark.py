# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Run a single benchmark and report it's run time to stdout.
"""

# This file, unlike all others, must be compatible with as many
# versions of Python as possible and have no external dependencies.
# This is the only bit of code from asv that is actually loaded into
# the benchmarking process.

import sys
import timeit
import unittest


if __name__ == '__main__':
    benchmark_dir = sys.argv[-2]
    benchmark_id = sys.argv[-1]
    sys.path.insert(0, benchmark_dir)

    benchmark = list(
        unittest.defaultTestLoader.loadTestsFromName(benchmark_id))[0]

    timefunc = timeit.default_timer
    number = 0
    repeat = timeit.default_repeat

    timer = timeit.Timer(
        stmt=getattr(benchmark, benchmark._testMethodName),
        setup=benchmark.setUp)

    if number == 0:
        # determine number so that 0.2 <= total time < 2.0
        number = 1
        for i in range(1, 10):
            if timer.timeit(number) >= 0.2:
                break
            number *= 10

    all_runs = timer.repeat(repeat, number)
    best = min(all_runs) / number
    sys.stdout.write(str(best) + '\n')
