# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

# Author: Pauli Virtanen, 2016

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import math

from .step_detect import solve_potts_approx


def compute_stats(samples):
    """
    Statistical analysis of measured samples.

    Parameters
    ----------
    samples : list of float
        List of total times (y) of benchmarks.

    Returns
    -------
    beta_hat : float
        Estimated time per iteration
    stats : dict
        Information on statistics of the estimator.

    """

    if len(samples) < 1:
        return None, None
    elif len(samples) == 1:
        return samples[0], None

    Y = list(samples)

    # Median and quantiles
    y_50, ci_50 = quantile_ci(Y, 0.5, alpha_min=0.99)
    y_25 = quantile(Y, 0.25)
    y_75 = quantile(Y, 0.75)

    # Look for big shifts in the time series
    min_size = max(5, len(Y)//5)
    gamma = quantile([abs(yp - y_50) for yp in Y], 0.5) * min_size
    if min_size <= len(Y):
        step_right, step_mu, _ = solve_potts_approx(Y, gamma=gamma, p=1, min_size=min_size)
    else:
        step_mu = [y_50]

    # Broaden the confidence interval by the detected steps
    ci_a, ci_b = ci_50
    ci_a -= y_50 - min(step_mu)
    ci_b += max(step_mu) - y_50

    # Produce results
    mean = sum(Y) / len(Y)
    var = sum((yp - mean)**2 for yp in Y) / len(Y)   # mle
    std = math.sqrt(var)

    result = y_50

    stats = {'ci_99': [ci_a, ci_b],
             'q_25': y_25,
             'q_75': y_75,
             'min': min(Y),
             'max': max(Y),
             'mean': mean,
             'std': std,
             'n': len(Y),
             'systematic': max(step_mu) - min(step_mu)}

    return result, stats


def get_err(result, stats):
    """
    Return an 'error measure' suitable for informing the user
    about the spread of the measurement results.
    """
    a, b = stats['q_25'], stats['q_75']
    return (b - a)/2


def is_different(stats_a, stats_b):
    """
    Check whether the samples are statistically different.

    This is a pessimistic check, and not statistically fully rigorous.
    The false negative rate is probably relatively high if the distributions 
    overlap significantly.

    Parameters
    ----------
    samples_a, samples_b
        Input samples
    p : float, optional
        Threshold p-value

    """

    # If confidence intervals overlap, reject
    ci_a = stats_a['ci_99']
    ci_b = stats_b['ci_99']

    if ci_a[1] >= ci_b[0] and ci_a[0] <= ci_b[1]:
        return False

    return True


def quantile_ci(x, q, alpha_min=0.99):
    """
    Compute a quantile and a confidence interval.

    Assumes independence, but otherwise nonparametric.

    Parameters
    ----------
    x : list of float
        Samples
    q : float
        Quantile to compute, in [0,1].
    alpha_min : float, optional
        Lower bound for the coverage.

    Returns
    -------
    m : float
        Quantile of x
    ci : tuple of floats
        Confidence interval (a, b), of coverage >= alpha_min.

    """

    y = sorted(x)
    n = len(y)

    cdf = 0

    alpha_min = min(alpha_min, 1 - alpha_min)
    pa = alpha_min / 2
    pb = 1 - pa

    a = y[0]
    b = y[-1]

    for k, yp in enumerate(y):
        cdf += binom_pmf(n, k, q)

        if cdf <= pa:
            if k < len(y) - 1:
                a = 0.5*(yp + y[k+1])
            else:
                a = yp

        if cdf >= pb:
            if k > 0:
                b = 0.5*(yp + y[k-1])
            else:
                b = yp
            break

    m = quantile(y, q)
    return m, (a, b)


def quantile(x, q):
    """
    Compute quantile/percentile of the data

    Parameters
    ----------
    x : list of float
        Data set
    q : float
        Quantile to compute, 0 <= q <= 1

    """
    if not 0 <= q <= 1:
        raise ValueError("Invalid quantile")

    y = sorted(x)
    n = len(y)

    z = (n - 1) * q
    j = int(math.floor(z))
    z -= j

    if j == n - 1:
        m = y[-1]
    else:
        m = (1 - z)*y[j] + z*y[j+1]

    return m


def binom_pmf(n, k, p):
    """Binomial pmf = (n choose k) p**k (1 - p)**(n - k)"""
    if not (0 <= k <= n):
        return 0
    if p == 0:
        return 1.0 * (k == 0)
    elif p == 1.0:
        return 1.0 * (k == n)

    logp = math.log(p)
    log1mp = math.log(1 - p)
    return math.exp(lgamma(1 + n) - lgamma(1 + n - k) - lgamma(1 + k)
                        + k*logp + (n - k)*log1mp)


_BERNOULLI = [1.0, -0.5, 0.166666666667, 0.0, -0.0333333333333, 0.0, 0.0238095238095]


def lgamma(x):
    """
    Log gamma function. Only implemented at integers.
    """

    if x <= 0:
        raise ValueError("Domain error")

    if x > 100:
        # DLMF 5.11.1
        r = 0.5 * math.log(2*math.pi) + (x - 0.5) * math.log(x) - x
        for k in range(1, len(_BERNOULLI)//2 + 1):
            r += _BERNOULLI[2*k] / (2*k*(2*k - 1) * x**(2*k - 1))
        return r

    # Fall back to math.factorial
    int_x = int(x)
    err_int = abs(x - int_x)

    if err_int < 1e-12 * abs(x):
        return math.log(math.factorial(int_x - 1))

    # Would need full implementation
    return float("nan")
