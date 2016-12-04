# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from itertools import product
import pytest

import asv.statistics as statistics


try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


try:
    from scipy import special, stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_compute_stats():
    np.random.seed(1)

    assert statistics.compute_stats([]) == (None, None)
    assert statistics.compute_stats([15.0]) == (15.0, None)

    for nsamples, true_mean in product([10, 50, 250], [0, 0.3, 0.6]):
        samples = np.random.randn(nsamples) + true_mean
        result, stats = statistics.compute_stats(samples)

        assert np.allclose(stats['systematic'], 0)
        assert np.allclose(stats['n'], len(samples))
        assert np.allclose(stats['mean'], np.mean(samples))
        assert np.allclose(stats['q_25'], np.percentile(samples, 25))
        assert np.allclose(stats['q_75'], np.percentile(samples, 75))
        assert np.allclose(stats['min'], np.min(samples))
        assert np.allclose(stats['max'], np.max(samples))
        assert np.allclose(stats['std'], np.std(samples, ddof=0))
        assert np.allclose(result, np.median(samples))

        ci = stats['ci_99']
        assert ci[0] <= true_mean <= ci[1]
        w = 12.0 * np.std(samples) / np.sqrt(len(samples))
        assert ci[1] - ci[0] < w

        err = statistics.get_err(result, stats)
        iqr = np.percentile(samples, 75) - np.percentile(samples, 25)
        assert np.allclose(err, iqr/2)


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_is_different():
    np.random.seed(1)

    # Smoke test is_different
    for true_mean, n, significant in [(0.05, 10, False), (0.05, 100, True), (0.1, 10, True)]:
        samples_a = 0 + 0.1 * np.random.rand(n)
        samples_b = true_mean + 0.1 * np.random.rand(n)
        result_a, stats_a = statistics.compute_stats(samples_a)
        result_b, stats_b = statistics.compute_stats(samples_b)
        assert statistics.is_different(stats_a, stats_b) == significant


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_quantile_ci():
    # Test the confidence intervals

    def get_z_exp(loc, scale, size):
        z = np.random.exponential(scale, size=size)
        z *= 2 * np.random.randint(0, 2, size=len(z)) - 1
        return loc + z

    def get_z_normal(loc, scale, size):
        z = np.random.normal(loc, scale, size=size)
        return z

    loc = 2.5
    scale = 2.5

    np.random.seed(1)

    for alpha_min in [0.5, 0.9, 0.99, 0.999]:
        for sampler in [get_z_exp, get_z_normal]:
            for size in [10, 30]:
                samples = []
                for k in range(300):
                    z = sampler(loc, scale, size)
                    m, ci = statistics.quantile_ci(z, 0.5, alpha_min)
                    assert np.allclose(m, np.median(z))
                    a, b = ci
                    samples.append(a <= loc <= b)

                alpha = sum(samples) / len(samples)

                # Order of magnitude should match
                assert 1 - alpha <= 5 * (1 - alpha_min), (alpha_min, sampler, size)


def test_quantile_ci_small():
    # Small samples should give min/max ci
    for n in range(1, 7):
        sample = list(range(n))
        m, ci = statistics.quantile_ci(sample, 0.5, 0.99)
        assert ci[0] == min(sample)
        assert ci[1] == max(sample)


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_quantile():
    np.random.seed(1)
    x = np.random.randn(50)
    for q in np.linspace(0, 1, 300):
        expected = np.percentile(x, 100 * q)
        got = statistics.quantile(x.tolist(), q)
        assert np.allclose(got, expected), q


@pytest.mark.skipif(not HAS_SCIPY, reason="Requires scipy")
def test_lgamma():
    x = np.arange(1, 5000)

    expected = special.gammaln(x)
    got = np.vectorize(statistics.lgamma)(x)

    assert np.allclose(got, expected, rtol=1e-12, atol=0)
    assert np.isnan(statistics.lgamma(1.2))


@pytest.mark.skipif(not HAS_SCIPY, reason="Requires scipy")
def test_binom_pmf():
    p = np.linspace(0, 1, 7)
    k = np.arange(0, 40, 5)[:,None]
    n = np.arange(0, 40, 5)[:,None,None]

    expected = stats.binom.pmf(k, n, p)
    got = np.vectorize(statistics.binom_pmf)(n, k, p)

    assert np.allclose(got, expected, rtol=1e-12, atol=0)
