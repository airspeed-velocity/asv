# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import random
import pytest

from asv.step_detect import (solve_potts, solve_potts_autogamma, solve_potts_approx,
                             detect_regressions, golden_search, median, rolling_median_dev,
                             L1Dist, detect_steps)
from asv import step_detect


try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

try:
    from asv import _rangemedian
    HAVE_RANGEMEDIAN = True
except ImportError:
    HAVE_RANGEMEDIAN = False


@pytest.fixture(params=[
    "python",
    pytest.mark.skipif(not HAVE_RANGEMEDIAN, reason="compiled asv._rangemedian required")("rangemedian")
])
def use_rangemedian(request):
    if request.param == "rangemedian":
        assert isinstance(step_detect.get_mu_dist([0], p=1), _rangemedian.RangeMedian)
        return True
    else:
        step_detect._rangemedian = None

        def restore():
            if HAVE_RANGEMEDIAN:
                step_detect._rangemedian = _rangemedian
        request.addfinalizer(restore)

        assert isinstance(step_detect.get_mu_dist([0], p=1), L1Dist)
        return False


@pytest.mark.skipif(not HAVE_NUMPY, reason="test needs numpy")
def test_solve_potts(use_rangemedian):
    try:
        np.random.seed(1234)
    except NameError:
        # work around a bug in old pypy/pytest
        pytest.skip("test needs numpy")
        return

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


@pytest.mark.skipif(not HAVE_NUMPY, reason="test needs numpy")
def test_autocorrelated():
    # Check that a low-amplitude cosine signal is not intepreted as
    # multiple steps
    j = np.arange(1000)
    y = 0.2 * np.cos(j/100.0) + 1.0 * (j >= 500)
    right, values, dists, gamma = solve_potts_autogamma(y.tolist(), p=1)
    assert right == [500, 1000]


@pytest.mark.skipif(not HAVE_NUMPY, reason="test needs numpy")
def test_detect_regressions(use_rangemedian):
    try:
        np.random.seed(1234)
    except NameError:
        # work around a bug in old pypy/pytest
        pytest.skip("test needs numpy")
        return

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
        steps = detect_steps(y)

        steps_lr = [(l, r) for l, r, _, _, _ in steps]
        k = steps[0][1]
        assert 990 <= k <= 1010
        assert steps_lr == [(0, k),
                            (k, 3234 + (seed % 123)),
                            (3234 + (seed % 123), 3264 + (seed % 53)),
                            (3264 + (seed % 53), 3350),
                            (3350, 3500 + (seed % 71)),
                            (3500 + (seed % 71), 3700),
                            (3700, 4000)]
        steps_v = [x[2] for x in steps]
        assert np.allclose(steps_v, [0.35, 0.05, 2.05, 4.05, 1.15, 4.05, 2.05], rtol=0.3)

        # The expected mean error is 0.7 <|U(0,1) - 1/2|> = 0.7/4
        steps_err = [x[4] for x in steps]
        assert np.allclose(steps_err, [0.7/4]*7, rtol=0.3)

        # Check detect_regressions
        new_value, best_value, regression_pos = detect_regressions(steps)
        assert regression_pos == [(3233 + (seed % 123), (3233 + (seed % 123) + 1), steps_v[1], steps_v[2]),
                                  (3499 + (seed % 71), 3499 + (seed % 71) + 1, steps_v[4], steps_v[5])]
        assert np.allclose(best_value, 0.7/2 - 0.3, rtol=0.3, atol=0)
        assert np.allclose(new_value, 0.7/2 - 0.3 + 2, rtol=0.3, atol=0)

def test_golden_search():
    def f(x):
        return 1 + x**3 + x**4
    x = golden_search(f, -1, -0.25, xatol=1e-5, ftol=0)
    assert abs(x - (-3/4)) < 1e-4
    x = golden_search(f, -0.25, 0.25, xatol=1e-5, ftol=0)
    assert abs(x - (-0.25)) < 1e-4


def rolling_median_dev_naive(items):
    for j in range(1, len(items)):
        m = median(items[:j])
        d = sum(abs(x - m) for x in items[:j])
        yield m, d


def test_rolling_median():
    random.seed(1)

    datasets = [
        [1, 1, 10, 3, 5, 1, -16, -3, 4, 9],
        [random.gauss(0, 1) for j in range(500)]
    ]

    for x in datasets:
        got = list(rolling_median_dev(x))
        expected = rolling_median_dev_naive(x)
        for j, b in enumerate(expected):
            a = got[j]
            assert abs(a[0] - b[0]) < 1e-10, (a, b)
            assert abs(a[1] - b[1]) < 1e-10, (a, b)


def test_l1dist(use_rangemedian):
    random.seed(1)

    datasets = [
        [1, 1, 10, 3, 5, 1, -16, -3, 4, 9],
        [random.gauss(0, 1) for j in range(50)]
    ]

    for dataset in datasets:
        dist = step_detect.get_mu_dist(dataset, p=1)
        dist.precompute(len(dataset)//2, 0, len(dataset)//2)

        for i in range(len(dataset)):
            for p, (m2, d2) in enumerate(rolling_median_dev(dataset[i:])):
                j = i + p

                m = dist.mu(i, j)
                d = dist.dist(i, j)

                assert m == m2, (i, j)
                assert abs(d - d2) < 1e-10, (i, j)


def test_regression_threshold():
    steps = [(0, 1,   1.0, 1.0, 0.0),
             (1, 2,   1.1, 1.1, 0.0),
             (2, 3,   2.0, 2.0, 0.0)]

    latest, best, pos = detect_regressions(steps, threshold=0.05)
    assert latest == 2
    assert best == 1
    assert pos == [(0, 1, 1.0, 1.1), (1, 2, 1.1, 2.0)]

    latest, best, pos = detect_regressions(steps, threshold=0.2)
    assert latest == 2
    assert best == 1
    assert pos == [(1, 2, 1.1, 2.0)]

    latest, best, pos = detect_regressions(steps, threshold=0.9)
    assert latest == 2
    assert best == 1
    assert pos == [(1, 2, 1.1, 2.0)]

    latest, best, pos = detect_regressions(steps, threshold=1.1)
    assert latest == None
    assert best == None
    assert pos == None
