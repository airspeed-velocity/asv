# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import warnings
from itertools import product
import math

import pytest

from asv.util import inf
import asv.statistics as statistics


try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


try:
    from scipy import integrate, special, stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_compute_stats():
    np.random.seed(1)

    assert statistics.compute_stats([], 1) == (None, None)
    assert statistics.compute_stats([15.0], 1) == (
        15.0, {'ci_99': [-inf, inf], 'max': 15.0, 'mean': 15.0, 'min': 15.0,
               'number': 1, 'q_25': 15.0, 'q_75': 15.0, 'repeat': 1, 'std': 0.0})

    for nsamples, true_mean in product([10, 50, 250], [0, 0.3, 0.6]):
        samples = np.random.randn(nsamples) + true_mean
        result, stats = statistics.compute_stats(samples, 42)

        assert stats['repeat'] == len(samples)
        assert stats['number'] == 42
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
    for true_mean, n, significant in [(0.01, 10, False), (0.05, 100, True), (0.1, 10, True)]:
        samples_a = 0 + 0.1 * np.random.rand(n)
        samples_b = true_mean + 0.1 * np.random.rand(n)
        result_a, stats_a = statistics.compute_stats(samples_a, 1)
        result_b, stats_b = statistics.compute_stats(samples_b, 1)
        assert statistics.is_different(None, None, stats_a, stats_b) == significant
        assert statistics.is_different(samples_a, samples_b, stats_a, stats_b) == significant


def _check_ci(estimator, sampler, nsamples=300):
    """
    Check whether confidence behaves as advertized.

    Draw random samples from a distribution and check how often the
    true value (assumed 0) falls in the estimated CI.

    Parameters
    ----------
    ci_estimator : callable(samples, alpha)
        Estimator returning ``(m, (a, b))`` for coverage alpha,
        for the estimate ``m`` and CI ``(a, b)``
    sampler : callable(size)
        Draw samples from a distribution with zero value for the true
        location parameter.
    nsamples : int, optional
        Number of samples to draw

    Yields
    ------
    size, alpha, alpha_got

    """
    alphas = [0.5, 0.1, 0.01]
    sizes = [2, 5, 10, 30, 100]

    for size, alpha in product(sizes, alphas):
        samples = []
        for k in range(nsamples):
            z = sampler(size)
            m, ci = estimator(z, alpha)
            a, b = ci
            assert a <= m <= b
            samples.append(a <= 0 <= b)

        alpha_got = 1 - sum(samples) / len(samples)

        yield size, alpha, alpha_got


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_quantile_ci():
    # Test the confidence intervals

    scale = 2.5

    def sample_exp(size):
        z = np.random.exponential(scale, size=size)
        z *= 2 * np.random.randint(0, 2, size=len(z)) - 1
        return z

    def sample_normal(size):
        return np.random.normal(0, scale, size=size)

    np.random.seed(1)

    for sampler in [sample_exp, sample_normal]:
        cis = _check_ci(lambda z, alpha: statistics.quantile_ci(z, 0.5, alpha),
                        sampler, nsamples=300)
        atol = 5/300
        for size, alpha, alpha_got in cis:
            if size < 20:
                assert 0 <= alpha_got <= 1.2*alpha
            else:
                assert 0.5*alpha - atol <= alpha_got <= 1.1*alpha + atol


def test_quantile_ci_small():
    # Small samples should give infinite ci
    for n in range(1, 7):
        sample = list(range(n))
        m, ci = statistics.quantile_ci(sample, 0.5, 0.99)
        assert ci[0] == -inf
        assert ci[1] == inf


def test_quantile_ci_r():
    # Compare to R
    x = [-2.47946614, -1.49595963, -1.02812482, -0.76592323, -0.09452743,  0.10732743,
         0.27798342, 0.50173779, 0.57829823, 0.60474948, 0.94695675, 1.20159789]

    # quantile(x, type=7, prob=p)
    q_20_e = -0.9756845
    q_50_e = 0.1926554
    q_80_e = 0.5994592

    # asht::quantileTest(x, prob=p, conf.level=0.8)$conf.int
    ci_20_80_e = [-2.47946614, -0.09452743]
    ci_50_80_e = [-0.7659232, 0.5782982]
    ci_80_80_e = [0.5017378, 1.2015979,]

    q_20, ci_20_80 = statistics.quantile_ci(x, 0.2, 0.8)
    q_50, ci_50_80 = statistics.quantile_ci(x, 0.5, 0.8)
    q_80, ci_80_80 = statistics.quantile_ci(x, 0.8, 0.8)

    assert q_20 == pytest.approx(q_20_e)
    assert q_50 == pytest.approx(q_50_e)
    assert q_80 == pytest.approx(q_80_e)

    assert ci_20_80 == pytest.approx(ci_20_80_e, abs=1e-4)
    assert ci_50_80 == pytest.approx(ci_50_80_e, abs=1e-4)
    assert ci_80_80 == pytest.approx(ci_80_80_e, abs=1e-4)


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


@pytest.mark.skipif(not HAS_NUMPY, reason="Requires numpy")
def test_laplace_posterior_ci():
    # Test the LaplacePosterior confidence intervals

    scale = 2.5

    def get_z_exp(size):
        """Samples from noise distribution assumed in LaplacePosterior"""
        z = np.random.exponential(scale, size=size)
        z *= 2 * np.random.randint(0, 2, size=len(z)) - 1
        return z

    def get_z_normal(size):
        """Samples from noise distribution not assumed in LaplacePosterior"""
        z = np.random.normal(0, scale, size=size)
        return z

    np.random.seed(41)

    def estimator(z, alpha):
        c = statistics.LaplacePosterior(z.tolist())
        a, b = c.ppf(alpha/2), c.ppf(1 - alpha/2)
        a = min(c.mle, a)  # force MLE inside CI
        b = max(c.mle, b)
        return c.mle, (a, b)

    for sampler in [get_z_exp, get_z_normal]:
        cis = _check_ci(estimator, sampler, nsamples=300)
        atol = 5/300
        for size, alpha, alpha_got in cis:
            if sampler == get_z_exp:
                # Result should be ok for the assumed distribution
                rtol = 0.25
            else:
                # For other distributions, order of magnitude should match
                rtol = 2.0

            assert np.allclose(alpha_got, alpha, atol=atol, rtol=rtol)


def test_laplace_posterior_basic():
    # Test the LaplacePosterior mle/cdf/ppf

    # even
    y = [1, 2, 3, 4, 5, 6][::-1]
    c = statistics.LaplacePosterior(y)
    assert abs(c.mle - 3.5) < 1e-8

    # odd
    y = [1, 2, 3, 4, 5][::-1]
    c = statistics.LaplacePosterior(y)
    assert abs(c.mle - 3) < 1e-8

    # check pdf vs cdf
    sx = 200
    dx = 1.0/sx
    cdf = 0
    for jx in range(-10*sx, 10*sx):
        cdf += c.pdf(dx*jx) * dx
        got = c.cdf(dx*jx)
        assert abs(cdf - got) < 3e-3
    assert abs(cdf - 1.0) < 1e-3

    # large input (must not cause overflows)
    y = list(range(500))
    c = statistics.LaplacePosterior(y)
    assert abs(c.mle - 249.5) < 1e-8
    assert abs(c.cdf(249.5) - 0.5) < 1e-8

    # check cdf sanity
    assert c.cdf(float('inf')) == 1.0
    assert c.cdf(-float('inf')) == 0.0
    assert abs(c.cdf(-1e9) - 0) < 1e-6
    assert abs(c.cdf(1e9) - 1) < 1e-6

    # check ppf
    for p in [0.0, 1e-3, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999, 1.0]:
        assert abs(c.cdf(c.ppf(p)) - p) < 1e-3

    t = c.ppf(1.1)
    assert t != t

    # check zero variance
    y = [1, 1, 1, 1, 1]
    c = statistics.LaplacePosterior(y)
    assert c.mle == 1
    assert c.pdf(1 - 1e-5) == 0
    assert c.pdf(1 + 1e-5) == 0
    assert c.cdf(1 - 1e-5) == 0
    assert c.cdf(1 + 1e-5) == 1.0
    assert c.ppf(1.0) == 1.0

    # one item
    y = [1]
    c = statistics.LaplacePosterior(y)
    assert c.cdf(1 - 1e-5) == 0
    assert c.cdf(1 + 1e-5) == 1.0

    # zero items
    with pytest.raises(ValueError):
        statistics.LaplacePosterior([])

    
@pytest.mark.skipif(not HAS_SCIPY, reason="Requires scipy")
def test_laplace_posterior_cdf():
    # Test the LaplacePosterior cdf vs pdf
    np.random.seed(1)
    y = np.random.randn(15).tolist()

    c = statistics.LaplacePosterior(y)

    num_cdf = lambda t: integrate.quad(c.pdf, -np.inf, t, limit=1000)[0]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=integrate.IntegrationWarning)

        for t in np.linspace(-5, 5, 70):
            x = c.cdf(t)
            assert abs(x - num_cdf(t)) < 1e-5
            assert abs(c.ppf(x) - t) < 1e-5


def test_mann_whitney_u_cdf():
    memo = {}

    def check_table(m, tbl):
        for u, row in enumerate(tbl):
            for nx, p in enumerate(row):
                n = nx + 1
                if p is None:
                    continue

                p2 = statistics.mann_whitney_u_cdf(m, n, u, memo=memo)
                assert p2 == pytest.approx(p, abs=1e-3, rel=0), (m, n, u, p2, p)

    # Tables from Mann & Whitney, Ann. Math. Statist. 18, 50 (1947).
    tbl = [[.250, .100, .050],
           [.500, .200, .100],
           [.750, .400, .200],
           [None, .600, .350],
           [None, None, .500],
           [None, None, .650]]
    check_table(3, tbl)

    tbl = [[.200, .067, .028, .014],
           [.400, .133, .057, .029],
           [.600, .267, .114, .057],
           [None, .400, .200, .100],
           [None, .600, .314, .171],
           [None, None, .429, .243],
           [None, None, .571, .343],
           [None, None, None, .443],
           [None, None, None, .557]]
    check_table(4, tbl)

    tbl = [[.167, .047, .018, .008, .004],
           [.333, .095, .036, .016, .008],
           [.500, .190, .071, .032, .016],
           [.667, .286, .125, .056, .028],
           [None, .429, .196, .095, .048],
           [None, .571, .286, .143, .075],
           [None, None, .393, .206, .111],
           [None, None, .500, .278, .155],
           [None, None, .607, .365, .210],
           [None, None, None, .452, .274],
           [None, None, None, .548, .345],
           [None, None, None, None, .421],
           [None, None, None, None, .500],
           [None, None, None, None, .579]]
    check_table(5, tbl)


@pytest.mark.skipif(not HAS_SCIPY, reason="Requires scipy")
def test_mann_whitney_u_scipy():
    # Scipy only has the large-sample limit...

    def check(x, y):
        u0, p0 = stats.mannwhitneyu(x, y, alternative='two-sided', use_continuity=False)

        u, p = statistics.mann_whitney_u(x.tolist(), y.tolist(), method='normal')
        assert u == u0
        assert p == pytest.approx(p0, rel=1e-9, abs=0)

        u, p = statistics.mann_whitney_u(x.tolist(), y.tolist(), method='exact')
        assert u == u0
        assert p == pytest.approx(p0, rel=5e-2, abs=5e-3)

        u, p = statistics.mann_whitney_u(x.tolist(), y.tolist())
        assert u == u0
        assert p == pytest.approx(p0, rel=5e-2, abs=5e-3)

    np.random.seed(1)
    x = np.random.randn(22)
    y = np.random.randn(23)

    check(x, y)
    check(x, y + 0.5)
    check(x, y - 2.5)


def test_binom():
    for n in range(10):
        for k in range(10):
            p = statistics.binom(n, k)
            if 0 <= k <= n:
                p2 = math.factorial(n) / math.factorial(k) / math.factorial(n - k)
            else:
                p2 = 0
            assert p == p2
