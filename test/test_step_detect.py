# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import pytest

from asv.step_detect import (solve_potts, solve_potts_autogamma, solve_potts_approx,
                             detect_regressions, golden_search, median, rolling_median)


try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


@pytest.mark.skip(not HAVE_NUMPY, reason="test needs numpy")
def test_solve_potts():
    np.random.seed(1234)

    # Easy case, exact solver
    y = [1, 1, 1, 2, 2, 2, 3, 3, 3]
    right, values, dists = solve_potts(y, gamma=0.1)
    assert right == [3, 6, 9]
    assert np.allclose(values, [1, 2, 3], atol=0)

    right, values, dists = solve_potts(y, gamma=8.0)
    assert right == [9]
    assert np.allclose(values, [2], atol=0)

    # l1 norm
    right, values, dists = solve_potts(y, gamma=0.1, p=1)
    assert right == [3, 6, 9]
    assert np.allclose(values, [1, 2, 3], atol=0)

    # Bigger case, exact solver
    t = np.arange(100)
    y0 = (+ 0.4 * (t >= 5)
          + 0.9 * (t >= 10)
          - 0.2 * (t >= 20)
          + 0.2 * (t >= 50)
          + 1.1 * (t >= 70))
    y = y0 + 0.1 * np.random.rand(y0.size)
    right, values, dists = solve_potts(y.tolist(), gamma=0.1)
    assert right == [5, 10, 20, 50, 70, 100]

    # Bigger case, approximative solver
    right, values, dists = solve_potts_approx(y.tolist(), gamma=0.1)
    assert right == [5, 10, 20, 50, 70, 100]

    # Larger case
    t = np.arange(3000)
    y0 = (+ 0.4 * (t >= 10)
          + 0.9 * (t >= 30)
          - 0.2 * (t >= 200)
          + 0.2 * (t >= 600)
          + 1.1 * (t >= 2500)
          - 0.5 * (t >= 2990))

    # Small amount of noise shouldn't disturb step finding
    y = y0 + 0.05 * np.random.randn(y0.size)
    right, values, dists, gamma = solve_potts_autogamma(y.tolist(), p=1)
    assert right == [10, 30, 200, 600, 2500, 2990, 3000]
    right, values, dists, gamma = solve_potts_autogamma(y.tolist(), p=2)
    assert right == [10, 30, 200, 600, 2500, 2990, 3000]

    # Large noise should prevent finding any steps
    y = y0 + 5.0 * np.random.randn(y0.size)
    right, values, dists, gamma = solve_potts_autogamma(y.tolist(), p=1)
    assert right == [3000]
    right, values, dists, gamma = solve_potts_autogamma(y.tolist(), p=2)
    assert right == [3000]

    # The routine shouldn't choke on datasets with 50k+ points.
    # Appending noisy data to weakly noisy data should retain the
    # steps in the former
    y = y0 + 0.05 * np.random.rand(y.size)
    ypad = 0.05 * np.random.randn(50000 - 3000)
    right, values, dists, gamma = solve_potts_autogamma(y.tolist() + ypad.tolist(), p=2)
    assert right == [10, 30, 200, 600, 2500, 2990, 3000, 50000]


@pytest.mark.skip(not HAVE_NUMPY, reason="test needs numpy")
def test_detect_regressions():
    for seed in [1234, 5678, 8901, 2345]:
        np.random.seed(seed)
        t = np.arange(4000)
        y = 0.7 * np.random.rand(t.size)

        y -= 0.3 * (t >= 1000)
        y += 2.0 * (t >= 3234 + (seed % 123))
        y += 2.0 * ((t >= 3264 + (seed % 53)) & (t < 3700))
        y -= 2.7 * ((t >= 3350) & (t < 3500 + (seed % 71)))

        y = y.tolist()
        y[123] = None
        y[1234] = np.nan
        new_value, jump_pos, best_value = detect_regressions(y)

        assert jump_pos == [3233 + (seed % 123), 3499 + (seed % 71)]
        assert np.allclose(best_value, 0.7/2 - 0.3, rtol=0.3, atol=0)
        assert np.allclose(new_value, 0.7/2 - 0.3 + 2, rtol=0.3, atol=0)


def test_golden_search():
    def f(x):
        return 1 + x**3 + x**4
    x = golden_search(f, -1, -0.25, xatol=1e-5, ftol=0)
    assert abs(x - (-3/4)) < 1e-4
    x = golden_search(f, -0.25, 0.25, xatol=1e-5, ftol=0)
    assert abs(x - (-0.25)) < 1e-4


def test_rolling_median():
    x = [1, 1, 10, 3, 5, 0.1, 0.6, -3, 4, 9]
    medians = rolling_median(x)
    for j, m in enumerate(medians):
        assert abs(m - median(x[:j+1])) < 1e-10
