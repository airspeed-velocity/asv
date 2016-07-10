# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-
r"""
Regression detection in ASV is based on detecting stepwise changes in
the graphs. The assumptions on the data are as follows: the curves are
piecewise constant plus random noise. We don't know the variance of
the noise nor the scaling of the data, but we assume the noise
amplitude is constant in time.

Luckily, step detection is a well-studied problem. In this
implementation, we mainly follow a variant of the approach outlined in
[Friedrich2008]_ and elsewhere. This provides a fast algorithm for
solving the piecewise fitting problem

.. math::
   :label: gamma-opt

   \mathop{\mathrm{argmin}}_{k,\{j\},\{\mu\}} \gamma k + \sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} |y_i - \mu_r|

The differences are: as we do not need exact solutions, we add
additional heuristics to work around the :math:`{\mathcal O}(n^2)`
scaling, which is too harsh for pure-Python code. For details, see
``asv.step_detect.solve_potts_approx``.  Moreover, we follow a
slightly different approach on obtaining a suitable number of
intervals, by selecting an optimal value for :math:`\gamma`, based on
a variant of the information criterion problem discussed in
[Yao1988]_.


.. [Friedrich2008] F. Friedrich et al.,
   ''Complexity Penalized M-Estimation: Fast Computation'',
   Journal of Computational and Graphical Statistics 17.1, 201-224 (2008).
   http://dx.doi.org/10.1198/106186008X285591
   https://www.nativesystems.inf.ethz.ch/pub/Main/FelixFriedrichPublications/mestimation.pdf

.. [Yao1988] Y.-C. Yao,
   ''Estimating the number of change-points via Schwarz criterion'',
   Statistics & Probability Letters 6, 181-189 (1988).
   http://dx.doi.org/10.1016/0167-7152(88)90118-6


Bayesian information
--------------------

To proceed, we need an argument by which to select a suitable
:math:`\gamma` in :eq:`gamma-opt`. Some of the literature on step
detection, e.g. [Yao1988]_, suggests results based on Schwarz information
criteria,

.. math::
   :label: ic-form

   \text{SC} = \frac{m}{2} \ln \sigma^2 + k \ln m = \text{min!}

where :math:`\sigma^2` is maximum likelihood variance estimator (if
noise is gaussian). For the implementation, see
``asv.step_detect.solve_potts_autogamma``.

What follows is a handwaving plausibility argument why such an
objective function makes sense, and how to end up with :math:`l_1`
rather than gaussians. Better approaches are probably to be found in
step detection literature.  If you have a better formulation,
contributions/corrections are welcome!

We assume a Bayesian model:

.. math::
   :label: prob-model

   P(\{y_i\}_{i=1}^m|\sigma,k,\{\mu_i\}_{i=1}^k,\{j_i\}_{i=1}^{k-1})
   =
   N
   \sigma^{-m}
   \exp(
   -\sigma^{-1}\sum_{r=1}^k\sum_{i=j_{r-1}+1}^{j_r} |y_i - \mu_r|
   )

Here, :math:`y_i` are the :math:`m` data points at hand, :math:`k` is
the number of intervals, :math:`\mu_i` are the values of the function
at the intervals, :math:`j_i` are the interval breakpoints;
:math:`j_0=0`, :math:`j_k=m`, :math:`j_{r-1}<j_r`. The noise is
assumed Laplace rather than gaussian, which results to the more
robust :math:`l_1` norm fitting rather than :math:`l_2`.  The noise
amplitude :math:`\sigma` is not known.
:math:`N` is a normalization constant that depends on :math:`m` but
not on the other parameters.

The optimal :math:`k` comes from Bayesian reasoning:
:math:`\hat{k} = \mathop{\mathrm{argmax}}_k P(k|\{y\})`, where

.. math::
   :label:

   P(k|\{y\}) = \frac{\pi(k)}{\pi(\{y\})}\int d\sigma (d\mu)^k \sum_{\{j\}}
   P(\{y\}|\sigma,k,\{\mu\},\{j\}) \pi(\sigma, \{\mu\},\{j\}|k)

The prior :math:`\pi(\{y\})` does not matter for :math:`\hat{k}`; the
other priors are assumed flat. We would need to estimate the behavior
of the integral in the limit :math:`m\to\infty`.  We do not succeed in
doing this rigorously here, although it might be done in the literature.

Consider first saddle-point integration over :math:`\{\mu\}`,
expanding around the max-likelihood values :math:`\mu_r^*`.
The max-likelihood estimates are medians of the data points in each interval.
Change in the exponent when :math:`\mu` is perturbed is

.. math::
   :label:

   \Delta = -\sigma^{-1}\sum_{r=1}^k \sum_{i=j_{r-1}+1}^{j_r}[|y_i-\mu^*_r - \delta\mu_r| - |y_i-\mu^*_r|]

Note that :math:`\sum_{i=j_{r-1}+1}^{j_r}
\mathrm{sgn}(y_i-\mu^*_r)=0`, so that response to small variations
:math:`\delta\mu_r` is :math:`m`-independent. For larger variations, we have

.. math::
   :label:

   \Delta = -\sigma^{-1}\sum_{r=1}^k N_r(\delta \mu_r) |\delta \mu_r|

where :math:`N_r(\delta\mu)=|\#\text{above}-\#\text{below}|` is the
difference in the number of points in the interval above vs. below the
perturbed median. Let us assume that in a typical case,
:math:`N_r(\delta\mu)\sim{}m_r\delta\mu/\sigma` where :math:`m_r` is
the number of points in the interval. This recovers a result we would
have obtained in the gaussian noise case

.. math::
   :label:

   \Delta \sim -\sigma^{-2} \sum_r m_r |\delta \mu_r|^2

For the gaussian case, this would not have required any questionable assumptions.
After integration over :math:`\{\delta\mu\}` we are left with

.. math::
   :label:

   \int(\ldots)
   \propto
   \int d\sigma \sum_{\{j\}}
   (2\pi)^{k/2}\sigma^k [m_1\cdots m_k]^{-1/2}
   P(\{y\}|\sigma,k,\{\mu_*\},\{j\})
   \pi(\sigma, \{j\}|k)

We now approximate the rest of the integrals/sums with only the
max-likelihood terms, and assume :math:`m_j^*\sim{}m/k`. Then,

.. math::
   :label: p-k-estimate

   \ln P(k|\{y\})
   &\simeq
   C_1(m) + C_2(k)
   +
   \frac{k}{2}\ln(2\pi) + k \ln \sigma_* - \frac{k}{2}\ln(m/k)
   +
   \ln P(\{y\}|\sigma_*,k,\{\mu_*\},\{j_*\})
   \\
   &\approx
   \tilde{C}_1(m) + \tilde{C}_2(k)
   -
   \frac{k}{2} \ln m
   +
   \ln P(\{y\}|\sigma_*,k,\{\mu_*\},\{j_*\})

where we neglect terms that don't affect asymptotics for
:math:`m\to\infty`, and :math:`C` are some constants not depending on
both :math:`m, k`. The result is of course the Schwarz criterion for
:math:`k` free model parameters. We can suspect that the factor
:math:`k/2` should be replaced by a different number, since we have
:math:`2k` parameters. If also the other integrals/sums can be 
approximated in the same way as the :math:`\{\mu\}` ones, we should
obtain the missing part.

Substituting in the max-likelihood value

.. math::
   :label:

    \sigma_* = \frac{1}{m} \sum_{r=1}^k\sum_{i=j_{r-1}^*+1}^{j_r^*} |y_i - \mu_r^*|

we get

.. math::
   :label:

   \ln P(k|\{y\})
   \sim
   C
   -
   \frac{k}{2} \ln m
   -
   m \ln\sum_{r=1}^k\sum_{i=j_{r-1}^*}^{j_r^*} |y_i - \mu_r^*|

This is now similar to :eq:`ic-form`, apart from numerical prefactors. The
final fitting problem then becomes

.. math::
   :label: bic-form

   \mathop{\mathrm{argmin}}_{k,\{j\},\{\mu\}} r(m) k + \ln\sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} |y_i - \mu_r|

with :math:`r(m) = \frac{\ln m}{2m}`. As we know this function
:math:`r(m)` is not necessarily completely correct, and it seems doing
the calculation rigorously requires more effort than can be justified
by the requirements of the application, we now take a pragmatic view and
fudge the function to :math:`r(m) = \beta \frac{\ln m}{m}` with
:math:`\beta` chosen so that things appear to work in practice
for the problem at hand.

According to [Friedrich2008]_, problem :eq:`bic-form` can be solved in
:math:`{\cal O}(n^3)` time.  This is too slow, however. We can however
approach this on the basis of the easier problem :eq:`gamma-opt`.  It
produces a family of solutions :math:`[k^*(\gamma), \{\mu^*(\gamma)\},
\{j^*(\gamma)\}]`.  We now evaluate :eq:`bic-form` restricted to the
curve parameterized by :math:`\gamma`.  In particular,
:math:`[\{\mu^*(\gamma)\}, \{j^*(\gamma)\}]` solves :eq:`bic-form`
under the constraint :math:`k=k^*(\gamma)`. If :math:`k^*(\gamma)`
obtains all values in the set :math:`\{1,\ldots,m\}` when
:math:`\gamma` is varied, the original problem is solved
completely. This probably is not a far-fetched assumption; in practice
it appears such Bayesian information criterion provides a reasonable
way for selecting a suitable :math:`\gamma`.


Autocorrelated noise
--------------------

Practical experience shows that the noise in the benchmark results can be
correlated. Often benchmarks are run for multiple commits at once, for
example the new commits at a given time, and the benchmark machine
does something else between the runs. Alternatively, the background
load from other processes on the machine varies with time.

To give a basic model for the noise correlations, we include
AR(1) Laplace noise in :eq:`prob-model`,

.. math::
   :label: autocorr-model

   P(\{y_i\}_{i=1}^m|\sigma,\rho,k,\{\mu_i\}_{i=1}^k,\{j_i\}_{i=1}^{k-1})
   =
   N
   \sigma^{-m}
   \exp(-\sigma^{-1}\sum_{r=1}^k\sum_{i=j_{r-1}+1}^{j_r} |\epsilon_{i,r} - \rho \epsilon_{i-1,r}|)

where :math:`\epsilon_{i,r}=y_i-\mu_{r}` with
:math:`\epsilon_{j_{r-1},r}=y_{j_{r-1}}-\mu_{r-1}` and
:math:`\epsilon_{j_0,1}=0` are the deviations from the stepwise
model. The correlation measure :math:`\rho` is unknown, but assumed to
be constant in :math:`(-1,1)`.

Since the parameter :math:`\rho` is global, it does not change the parameter
counting part of the Schwarz criterion.  The maximum likelihood term however
does depend on :math:`\rho`, so that the problem becomes:

.. math::
   :label: bic-form-autocorr

   \mathop{\mathrm{argmin}}_{k,\rho,\{j\},\{\mu\}} r(m) k + \ln\sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} |\epsilon_{i,r} - \rho\epsilon_{i-1,r}|

To save computation time, we do not solve this optimization problem
exactly. Instead, we again minimize along the :math:`\mu_r^*(\gamma)`,
:math:`j_r^*(\gamma)` curve provided by the solution to
:eq:`gamma-opt`, and use :eq:`bic-form-autocorr` only in selecting the
optimal value of the :math:`\gamma` parameter.

The minimization vs. :math:`\rho` can be done numerically for given
:math:`\mu_r^*(\gamma)`, :math:`j_r^*(\gamma)`. This minimization step
is computationally cheap compared to the piecewise fit, so including
it will not significantly change the runtime of the total algorithm.

Postprocessing
--------------

For the purposes of regression detection, we do not report all steps
the above approach provides. For details, see
``asv.step_detect.detect_regressions``.

"""

from __future__ import absolute_import, division, unicode_literals, print_function

import math
import collections
import heapq
import six

try:
    from . import _rangemedian
except ImportError:
    _rangemedian = None


#
# Detecting regressions
#

def detect_steps(y):
    """
    Detect steps in a (noisy) signal.

    Parameters
    ----------
    y : list of float, none or nan
        Single benchmark result series, with possible missing data

    Returns
    -------
    steps : list of (left_pos, right_pos, value, err_est)
        List containing a decomposition of the input data to a piecewise
        constant function. Each element contains the left (inclusive) and
        right (exclusive) bounds of a segment, the average value on 
        the segment and the l1 error estimate, <|Y - avg|>. Missing data
        points are not necessarily contained in any segment; right_pos-1
        is the last non-missing data point.

    """

    index_map = {}
    y_filtered = []
    for j, x in enumerate(y):
        if x is None or x != x:
            # None or NaN: missing data
            continue
        index_map[len(y_filtered)] = j
        y_filtered.append(x)

    # Find piecewise segments
    right, values, dists, gamma = solve_potts_autogamma(y_filtered, p=1)

    # Extract the steps, mapping indices back etc.
    steps = []
    l = 0
    for r, v, d in zip(right, values, dists):
        steps.append((index_map[l], index_map[r-1] + 1,
                          v,
                          min(y_filtered[l:r]),
                          abs(d/(r - l))))
        l = r
    return steps


def detect_regressions(steps, threshold=0):
    """
    Detect regressions in a (noisy) signal.

    Parameters
    ----------
    steps : list of (left, right, value, min, error)
        List of steps computed by detect_steps, or equivalent
    threshold : float
        Relative threshold for reporting regressions. Filter out jumps
        whose relative size is smaller than threshold, if they are not
        necessary to explain the difference between the best and the latest
        values.

    Returns
    -------
    latest_value
        Latest value
    best_value
        Best value
    regression_pos : list of (before, after, value_before, value_after)
        List of positions between which the value increased. The first item
        corresponds to the last position at which the best value was obtained.

    """
    # Find best value and compare to the most recent one
    best_v = None
    best_err = None
    cur_err = None
    cur_v = None

    prev_v = None
    prev_err = None

    if steps:
        last_v = steps[-1][2]
    else:
        last_v = None

    regression_pos = []

    prev_r = None
    for l, r, cur_v, cur_min, cur_err in steps:
        if best_v is None or cur_min <= best_v + best_err:
            # Found best value (modulo errors)
            best_v = cur_v
            best_err = cur_err
            regression_pos = []
        elif (not regression_pos or (prev_v is not None and
                cur_v > prev_v + max(cur_err, prev_err) and
                prev_v < last_v - max(cur_err, prev_err))):
            # Found an upward jump
            regression_pos.append((prev_r - 1, l, prev_v, cur_v))

        prev_r = r
        prev_v = cur_v
        prev_err = cur_err

    # Apply threshold
    if best_v is not None:
        if best_v != 0:
            min_jump = threshold * abs(best_v)
        else:
            min_jump = threshold * abs(last_v)

        regression_pos.sort(key=lambda pos: pos[3] - pos[2], reverse=True)
        explained = 0
        for j, pos in enumerate(regression_pos):
            jump = pos[3] - pos[2]
            if jump < min_jump and explained >= last_v - best_v - min_jump:
                regression_pos = regression_pos[:j]
                break
            explained += jump
        regression_pos.sort(key=lambda pos: pos[0])

    # Return results
    if cur_v is None or best_v is None or cur_v <= best_v + max(cur_err, best_err) or not regression_pos:
        return (None, None, None)
    else:
        return (cur_v, best_v, regression_pos)


#
# Fitting piecewise constant functions to noisy data
#

def solve_potts(y, gamma, p=2, min_size=2, max_size=None,
                min_pos=None, max_pos=None, mu_dist=None):
    """Fit penalized stepwise constant function (Potts model) to data.

    Given a time series y = {y_1, ..., y_n}, fit series x = {x_1, ..., x_n}
    by minimizing the cost functional::

        F[x] = gamma * J(x) + sum(|y - x|**p)

    where J(x) is the number of jumps (x_{j+1} != x_j) in x.

    The algorithm used is described in Ref. [1]_, it uses dynamic
    programming to find an exact solution to the problem (within the
    constraints specified).

    For p=2 norm, the performance is O(n**2), or
    O((max_pos-min_pos)*(min_size-max_size+1)) if constrained.

    For p=1 norm, it is O(n**2 log n) and the constants in front are
    bigger, due to the somewhat sub-optimal (= in Python) way median
    and absolute sum computations are done.

    Parameters
    ----------
    y : list of floats
        Input data series
    gamma : float
        Penalty parameter.
    min_size : int, optional
        Minimum interval size to consider
    max_size : int, optional
        Maximum interval size to consider
    mu_dist : *Dist, optional
        Precomputed interval means/medians and cost function values
    min_pos : int, optional
        Start point (inclusive) for the interval grid
    max_pos : int, optional
        End point (exclusive) for the interval grid

    Returns
    -------
    right : list
        List of (exclusive) right bounds of the intervals
    values : list
        List of values of the intervals
    dist : list
        List of ``sum(|y - x|**p)`` for each interval.
    mu_dist : *Dist
        Precomputed interval means/medians and cost function values

    References
    ----------
    [1] F. Friedrich et al., "Complexity Penalized M-Estimation: Fast Computation",
        Journal of Computational and Graphical Statistics 17.1, 201-224 (2008).

    """

    inf = float('inf')

    if len(y) == 0:
        return [], [], []

    if min_pos is None:
        min_pos = 0

    if max_pos is None:
        max_pos = len(y)

    if mu_dist is None:
        mu_dist = get_mu_dist(y, p)

    if max_size is None:
        max_size = len(y)

    mu_dist.precompute(max_size, min_pos, max_pos)
    mu, dist = mu_dist.mu, mu_dist.dist

    if min_size >= max_pos - min_pos:
        return [len(y)], [mu(0,len(y)-1)], [dist(0,len(y)-1)]

    # Perform the Bellman recursion for the optimal partition.
    # Routine "Find best partition" in [1]
    #
    # Computes:
    #
    # p : list, length n
    #     Set of intervals, represented as follows:
    #     For interval (inclusive) right edge r in {0, ..., n-1},
    #     the best (exclusive) left edge is at l=p[r].
    #     Where intervals overlap, the rightmost one has priority.

    if hasattr(mu_dist, 'find_best_partition'):
        p = mu_dist.find_best_partition(gamma, min_size, max_size, min_pos, max_pos)
    else:
        i0 = min_pos
        i1 = max_pos

        B = [-gamma]*(i1 - i0 + 1)
        p = [0]*(i1 - i0)
        for r in range(i0, i1):
            B[r+1-i0] = inf
            a = max(r + 1 - max_size, i0)
            b = max(r + 1 - min_size + 1, i0)
            for l in range(a, b):
                b = B[l-i0] + gamma + dist(l, r)
                if b <= B[r+1-i0]:
                    B[r+1-i0] = b
                    p[r-i0] = l - 1

    # Routine "Segmentation from partition" in [1]
    # Convert interval representation computed above
    # to a list of intervals and values.
    r = len(p) - 1 + min_pos
    l = p[r - min_pos]
    right = []
    values = []
    dists = []
    while r >= min_pos:
        right.append(r + 1)
        values.append(mu((l + 1), r))
        dists.append(dist((l + 1), r))
        r = l
        l = p[r - min_pos]
    right.reverse()
    values.reverse()
    dists.reverse()

    return right, values, dists


def solve_potts_autogamma(y, beta=None, **kw):
    """Solve Potts problem with automatically determined gamma.

    The optimal value is determined by minimizing the information measure::

        f(gamma) = beta J(x(gamma)) + log sum(abs(x(gamma) - y)**p)

    where x(gamma) is the solution to the Potts problem for a fixed
    gamma. The minimization is only performed rather roughly.

    Parameters
    ----------
    beta : float or 'bic'
         Penalty parameter. Default is 5*ln(n)/n, similar to Bayesian
         information criterion for gaussian model with unknown variance
         assuming 5 DOF per breakpoint.

    """
    n = len(y)

    if n == 0:
        return [], [], [], None

    mu_dist = get_mu_dist(y, kw.get('p', 2))
    mu, dist = mu_dist.mu, mu_dist.dist

    if beta is None:
        beta = 4 * math.log(n) / n

    gamma_0 = dist(0, n-1)

    best_r = [None]
    best_v = [None]
    best_d = [None]
    best_obj = [float('inf')]
    best_gamma = [None]

    def f(x):
        gamma = gamma_0 * math.exp(x)
        r, v, d = solve_potts_approx(y, gamma=gamma, mu_dist=mu_dist, **kw)

        # MLE fit noise correlation
        def sigma_star(rights, values, rho):
            """
            |E_0| + sum_{j>0} |E_j - rho E_{j-1}|
            """
            l = 1
            E_prev = y[0] - values[0]
            s = abs(E_prev)
            for r, v in zip(rights, values):
                for yv in y[l:r]:
                    E = yv - v
                    s += abs(E - rho*E_prev)
                    E_prev = E
                l = r
            return s

        rho_best = golden_search(lambda rho: sigma_star(r, v, rho), -1, 1,
                                 xatol=0.05, expand_bounds=True)

        # Objective function
        obj = beta*len(r) + math.log(1e-300 + sigma_star(r, v, rho_best))

        # Done
        if obj < best_obj[0]:
            best_r[0] = r
            best_v[0] = v
            best_d[0] = d
            best_gamma[0] = gamma
            best_obj[0] = obj
        return obj

    # Try to find best gamma (golden section search on log-scale); we
    # don't need an accurate value for it however
    a = math.log(0.1/n)
    b = 0.0
    golden_search(f, a, b, xatol=abs(a)*0.1, ftol=0, expand_bounds=True)
    return best_r[0], best_v[0], best_d[0], best_gamma[0]


def solve_potts_approx(y, gamma=None, p=2, **kw):
    """
    Fit penalized stepwise constant function (Potts model) to data
    approximatively, in linear time.

    Do this by running the exact solver using a small maximum interval
    size, and then combining consecutive intervals together if it
    decreases the cost function.
    """
    n = len(y)

    if n == 0:
        return [], [], []

    mu_dist = kw.get('mu_dist')
    if mu_dist is None:
        mu_dist = get_mu_dist(y, p=p)
        kw['mu_dist'] = mu_dist

    if gamma is None:
        mu, dist = mu_dist.mu, mu_dist.dist
        gamma = 3 * dist(0,n-1) * math.log(n) / n

    right, values, dists = solve_potts(y, gamma, p=p, max_size=20, **kw)
    return merge_pieces(gamma, right, values, dists, mu_dist, max_size=20)


def merge_pieces(gamma, right, values, dists, mu_dist, max_size):
    """
    Combine consecutive intervals in Potts model solution, if doing
    that reduces the cost function.
    """
    mu, dist = mu_dist.mu, mu_dist.dist

    right = list(right)

    # Combine consecutive intervals, if it results to decrease of cost
    # function
    while True:
        min_change = 0
        min_change_j = len(right)

        l = 0
        for j in range(1, len(right)):
            if min_change_j < j - 2:
                break

            # Check whether merging consecutive intervals results to
            # decrease in the cost function
            change = dist(l, right[j]-1) - (dist(l, right[j-1]-1) + dist(right[j-1], right[j]-1) + gamma)
            if change <= min_change:
                min_change = change
                min_change_j = j-1
            l = right[j-1]

        if min_change_j < len(right):
            del right[min_change_j]
        else:
            break

    # Check whether perturbing boundary positions leads to improvement
    # in the cost function. The restricted Potts minimization can
    # return sub-optimal boundaries due to the interval maximum size
    # restriction.
    l = 0
    for j in range(1, len(right)):
        prev_score = dist(l, right[j-1]-1) + dist(right[j-1], right[j]-1)
        new_off = 0
        for off in range(-max_size, max_size+1):
            if right[j-1] + off - 1 <= l or right[j-1] + off >= right[j] - 1 or off == 0:
                continue
            new_score = dist(l, right[j-1]+off-1) + dist(right[j-1]+off, right[j]-1)
            if new_score < prev_score:
                new_off = off
                prev_score = new_score

        if new_off != 0:
            right[j-1] += new_off

        l = right[j-1]

    # Rebuild values and dists lists
    l = 0
    values = []
    dists = []
    for j in range(len(right)):
        dists.append(dist(l, right[j]-1))
        values.append(mu(l, right[j]-1))
        l = right[j]

    return right, values, dists


class L1Dist(object):
    """
    Fast computations for::

        mu(l, r) = median(y[l:r+1])
        dist(l, r) = sum(abs(x - mu(l, r)) for x in y[l:r+1])

    We do not use here an approach that has asymptotically optimal
    performance; at least O(n**2 * log(n)) would be achievable, whereas
    we have here O(n**3).  The asymptotic performance does not matter
    for solve_potts_approx, which only looks at small windows of the
    data. It is more important to try to optimize the constant
    prefactors, which for Python means minimal code.

    """
    def __init__(self, y):
        self.y = y

        class mu_dict(collections.defaultdict):
            def __missing__(self, a):
                l, r = a
                v = median(y[l:r+1])
                self[a] = v
                return v

        mu = mu_dict()

        class dist_dict(collections.defaultdict):
            def __missing__(self, a):
                l, r = a
                m = mu[l, r]
                v = sum(abs(x - m) for x in y[l:r+1])
                self[a] = v
                return v

        self.mu_memo = mu
        self.dist_memo = dist_dict()

    def mu(self, *a):
        return self.mu_memo[a]

    def dist(self, *a):
        return self.dist_memo[a]

    def precompute(self, max_size, min_pos, max_pos):
        y = self.y

        if (min_pos, min_pos+max_size) in self.mu_memo:
            # The entries were likely already precomputed
            return

        # Precompute interval medians. Does not matter much for
        # solve_potts_approx, but doesn't hurt either.
        for j in range(min_pos, max_pos):
            median_dev = rolling_median_dev(y[j:min(max_pos,(j+(max_size+1)))])
            for p, (m, d) in enumerate(median_dev):
                if j+p > j+max_size:
                    break
                self.mu_memo[j,j+p] = m
                self.dist_memo[j,j+p] = d


class L2Dist(object):
    """
    Fast computations for::

        mu(l, r) = mean(y[l:r+1])
        dist(l, r) = sum((x - mu(l, r))**2 for x in y[l:r+1])

    """
    def __init__(self, y):
        self.y = y
        self.cum_y = None
        self.cum_y2 = None
        self.precompute(None, None, None)

    def precompute(self, max_size, min_pos, max_pos):
        if self.cum_y is not None:
            return

        cum_y = [0]
        cum_y2 = [0]
        s = 0
        s2 = 0
        for x in self.y:
            s += x
            s2 += x**2
            cum_y.append(s)
            cum_y2.append(s2)

        self.cum_y = cum_y
        self.cum_y2 = cum_y2

    def mu(self, l, r):
        """
        mean(y[l:r+1])
        """
        return (self.cum_y[r+1] - self.cum_y[l]) / (r + 1 - l)

    def dist(self, l, r):
        """
        sum((y[l:r+1] - mean(y[l:r+1]))**2)
        """
        # This way to compute it is in principle susceptible
        # to rounding errors, but we have to be O(1) fast here
        return abs(self.cum_y2[r+1] - self.cum_y2[l] - (self.cum_y[r+1] - self.cum_y[l])**2 / (r + 1 - l))


def get_mu_dist(y, p):
    if p == 1:
        if _rangemedian is not None:
            return _rangemedian.RangeMedian(y)
        else:
            return L1Dist(y)
    elif p == 2:
        return L2Dist(y)
    else:
        raise ValueError("invalid value for p")


def median(items):
    """Note: modifies the input list!"""
    items.sort()
    k = len(items)//2
    if len(items) % 2 == 0:
        return (items[k] + items[k - 1]) / 2
    else:
        return items[k]


def rolling_median_dev(items):
    """
    Compute median(items[:j]), deviation[j]) for j in range(1, len(items))
    in O(n log n) time.

    deviation[j] == sum(abs(x - median(items[:j])) for x in items[:j])
    """
    min_heap = []
    max_heap = []
    min_heap_sum = 0   # equal to -sum(min_heap)
    max_heap_sum = 0   # equal to sum(max_heap)
    s = iter(items)
    try:
        while True:
            # Odd
            v = six.next(s)
            min_heap_sum += v
            v = -heapq.heappushpop(min_heap, -v)
            min_heap_sum -= v
            heapq.heappush(max_heap, v)
            max_heap_sum += v
            # Ensure d >= 0 despite rounding error
            d = max(0, max_heap_sum - min_heap_sum - max_heap[0])
            yield (max_heap[0], d)

            # Even
            v = six.next(s)
            max_heap_sum += v
            v = heapq.heappushpop(max_heap, v)
            max_heap_sum -= v
            heapq.heappush(min_heap, -v)
            min_heap_sum += v
            d = max(0, max_heap_sum - min_heap_sum)
            yield ((max_heap[0] - min_heap[0])/2, d)
    except StopIteration:
        return


def golden_search(f, a, b, xatol=1e-6, ftol=1e-8, expand_bounds=False):
    """
    Find minimum of a function on interval [a, b]
    using golden section search.

    If expand_bounds=True, expand the interval so that the function is
    first evaluated at x=a and x=b.
    """

    ratio = 2 / (1 + math.sqrt(5))

    if not expand_bounds:
        x0 = a
        x3 = b
    else:
        x0 = (ratio * a - (1 - ratio) * b) / (2*ratio - 1)
        x3 = (ratio * b - (1 - ratio) * a) / (2*ratio - 1)

    x1 = ratio * x0 + (1 - ratio) * x3
    x2 = (1 - ratio) * x0 + ratio * x3

    f1 = f(x1)
    f2 = f(x2)

    f0 = max(abs(f1), abs(f2))

    while True:
        if abs(x0 - x3) < xatol or abs(f1 - f2) < ftol*f0:
            break

        if f2 < f1:
            x0 = x1
            x1 = x2
            x2 = ratio * x1 + (1 - ratio) * x3
            f1 = f2
            f2 = f(x2)
        else:
            x3 = x2
            x2 = x1
            x1 = ratio * x2 + (1 - ratio) * x0
            f2 = f1
            f1 = f(x1)

    if f2 < f1:
        return x2
    else:
        return x1


def _plot_potts(x, sol):
    import numpy as np
    import matplotlib.pyplot as plt

    t = np.arange(len(x))

    plt.clf()
    plt.plot(t, x, 'k.')

    l = 0
    for r, v in zip(sol[0], sol[1]):
        plt.plot([l, r-1], [v, v], 'b-o', hold=1)
        l = r
