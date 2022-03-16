# Licensed under a 3-clause BSD style license - see LICENSE.rst
r"""Regression detection in ASV is based on detecting stepwise changes
in the graphs. The assumptions on the data are as follows: the curves
are piecewise constant plus random noise. We don't know the scaling of
the data or the amplitude of the noise, but assume the relative weight
of the noise amplitude is known for each data point.

ASV measures the noise amplitude of each data point, based on a number
of samples. We use this information for weighting the different data
points:

.. math::

   \sigma_j = \sigma \mathrm{CI}_{99} = \sigma / w_j

i.e., we assume the uncertainty in each measurement point is
proportional to the estimated confidence interval for each data point.
Their inverses are taken as the relative weights ``w_j``. If ``w_j=0``
or undefined, we replace it with the median weight, or with ``1`` if
all are undefined. The step detection algorithm determines the
absolute noise amplitude itself based on all available data, which is
more robust than relying on the individual measurements.

Step detection is a well-studied problem. In this implementation, we
mainly follow a variant of the approach outlined in [Friedrich2008]_
and elsewhere. This provides a fast algorithm for solving the
piecewise weighted fitting problem

.. math::
   :label: gamma-opt

   \mathop{\mathrm{argmin}}_{k,\{j\},\{\mu\}} \gamma k +
   \sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} w_i |y_i - \mu_r|

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
   -\sigma^{-1}\sum_{r=1}^k\sum_{i=j_{r-1}+1}^{j_r} w_i |y_i - \mu_r|
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
   :label: p-k-prob

   P(k|\{y\}) = \frac{\pi(k)}{\pi(\{y\})}\int d\sigma (d\mu)^k \sum_{\{j\}}
   P(\{y\}|\sigma,k,\{\mu\},\{j\}) \pi(\sigma, \{\mu\},\{j\}|k)

The prior :math:`\pi(\{y\})` does not matter for :math:`\hat{k}`; the
other priors are assumed flat. We would need to estimate the behavior
of the integral in the limit :math:`m\to\infty`.  We do not succeed in
doing this rigorously here, although it might be done in the literature.

Consider first saddle-point integration over :math:`\{\mu\}`,
expanding around the max-likelihood values :math:`\mu_r^*`.
The max-likelihood estimates are the weighted medians of the data points in each interval.
Change in the exponent when :math:`\mu` is perturbed is

.. math::
   :label:

   \Delta = -\sigma^{-1}\sum_{r=1}^k
            \sum_{i=j_{r-1}+1}^{j_r}w_i[|y_i-\mu^*_r - \delta\mu_r| - |y_i-\mu^*_r|]

Note that :math:`\sum_{i=j_{r-1}+1}^{j_r}
w_i\mathrm{sgn}(y_i-\mu^*_r)=0`, so that response to small variations
:math:`\delta\mu_r` is :math:`m`-independent. For larger variations, we have

.. math::
   :label:

   \Delta = -\sigma^{-1}\sum_{r=1}^k N_r(\delta \mu_r) |\delta \mu_r|

where :math:`N_r(\delta\mu)=\sum_{i} w_i s_i` where :math:`s_i = \pm1` depending on whether
:math:`y_i` is above or below the perturbed median. Let us assume that in a typical case,
:math:`N_r(\delta\mu)\sim{}m_r\bar{W}_r^2\delta\mu/\sigma`
where :math:`\bar{W}_r = \frac{1}{m_r}\sum_i w_i` is
the average weight of the interval and :math:`m_r` the number of points in the interval.
This recovers a result we would
have obtained in the gaussian noise case

.. math::
   :label:

   \Delta \sim -\sigma^{-2} \sum_r W_r^2 m_r |\delta \mu_r|^2

For the gaussian case, this would not have required any questionable assumptions.
After integration over :math:`\{\delta\mu\}` we are left with

.. math::
   :label:

   \int(\ldots)
   \propto
   \int d\sigma \sum_{\{j\}}
   (2\pi)^{k/2}\sigma^k [\bar{W}_1\cdots \bar{W}_k]^{-1} [m_1\cdots m_k]^{-1/2}
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
   \frac{k}{2}\ln(2\pi) - \frac{k}{2} \ln(m/k) - k \ln \bar{W}
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

    \sigma_* = \frac{1}{m} \sum_{r=1}^k\sum_{i=j_{r-1}^*+1}^{j_r^*} w_i|y_i - \mu_r^*|

we get

.. math::
   :label:

   \ln P(k|\{y\})
   \sim
   C
   -
   \frac{k}{2} \ln m
   -
   m \ln\sum_{r=1}^k\sum_{i=j_{r-1}^*}^{j_r^*} w_i |y_i - \mu_r^*|

This is now similar to :eq:`ic-form`, apart from numerical prefactors.
The final fitting problem then becomes

.. math::
   :label: bic-form

   \mathop{\mathrm{argmin}}_{k,\{j\},\{\mu\}} r(m) k +
   \ln\sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} w_i |y_i - \mu_r|

with :math:`r(m) = \frac{\ln m}{2m}`.
Note that it is invariant vs. rescaling of weights :math:`w_i\mapsto{}\alpha{}w_i`,
i.e., the invariance of the original problem is retained.
As we know this function
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


Overfitting
-----------

It's possible to fit any data perfectly by choosing size-1 intervals,
one per each data point.  For such a fit, the logarithm :eq:`bic-form`
gives :math:`-\infty` which then always minimizes SC.  This artifact
of the model above needs special handling.

Indeed, for :math:`\sigma\to0`, :eq:`prob-model` reduces to

.. math::
   :label: prob-model-2

   P(\{y_i\}_{i=1}^m|\sigma,k,\{\mu_i\}_{i=1}^k,\{j_i\}_{i=1}^{k-1})
   =
   \prod_{r=1}^k \prod_{i=j_{r-1} + 1}^{j_r} \delta(y_i - \mu_r)

which in :eq:`p-k-prob` gives a contribution (assuming no repeated y-values)

.. math::
   :label: p-k-prob-2

   P(k|\{y\}) = \frac{\pi(n)}{\pi(\{y\})}\delta_{n,k}\int d\sigma
   \pi(\sigma, \{y\},\{i\}|n) f(\sigma)
   +
   \ldots

with :math:`f(\sigma)\to1` for :math:`\sigma\to0`.  A similar situation
occurs also in other cases where perfect fitting occurs (repeated
y-values).  With the flat, scale-free prior
:math:`\pi(\ldots)\propto1/\sigma` used above, the result is
undefined.

A simple fix is to give up complete scale free-ness of the results,
i.e., fixing a minimal noise level
:math:`\pi(\sigma,\{\mu\},\{j\}|k)\propto\theta(\sigma-\sigma_0)/\sigma` with some
:math:`\sigma_0(\{\mu\},\{j\},k)>0`. The effect in the
:math:`\sigma` integral is cutting off the log-divergence, so that
with sufficient accuracy we can in :eq:`bic-form` replace

.. math::
   :label: bic-form-2

   \ln \sigma \mapsto \ln(\sigma_0 + \sigma)

Here, we fix a measurement accuracy floor with the following guess:
``sigma_0 = 0.1 * w0 * min(abs(diff(mu)))`` and ``sigma_0 = 0.001 * w0
* abs(mu)`` when there is only a single interval. Here, ``w0`` is the
median weight.

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

   \mathop{\mathrm{argmin}}_{k,\rho,\{j\},\{\mu\}} r(m) k +
   \ln\sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} |\epsilon_{i,r} - \rho\epsilon_{i-1,r}|

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

Making use of measured variance
-------------------------------

``asv`` measures also variance in the timings.  This information is
currently used to provide relative data weighting (see above).

"""


import math
import collections
import heapq
from statistics import median

try:
    from . import _rangemedian
except ImportError:
    _rangemedian = None


#
# Detecting regressions
#

def detect_steps(y, w=None):
    """
    Detect steps in a (noisy) signal.

    Parameters
    ----------
    y : list of float, none or nan
        Single benchmark result series, with possible missing data
    w : list of float, none or nan
        Data point relative weights. Missing weights are set equal
        to the median weight.

    Returns
    -------
    steps : list of (left_pos, right_pos, value, min_value, err_est)
        List containing a decomposition of the input data to a piecewise
        constant function. Each element contains the left (inclusive) and
        right (exclusive) bounds of a segment, the average value on
        the segment, the minimum value in the segment, and the l1 error
        estimate, <|Y - avg|>. Missing data points are not necessarily
        contained in any segment; right_pos-1 is the last non-missing data
        point.

    """

    index_map = {}
    y_filtered = []
    for j, x in enumerate(y):
        if x is None or x != x:
            # None or NaN: missing data
            continue
        if w is not None and w[j] is not None and (w[j] <= 0):
            # non-positive weight: consider as missing data
            continue
        index_map[len(y_filtered)] = j
        y_filtered.append(x)

    # Weights
    if w is None:
        w_filtered = [1] * len(y_filtered)
    else:
        # Fill-in and normalize weights
        w_valid = [ww for ww in w if ww is not None and ww == ww]
        if w_valid:
            w_median = median(w_valid)
            if w_median == 0:
                w_median = 1.0
        else:
            w_median = 1.0

        w_filtered = [1.0] * len(y_filtered)
        for j in range(len(w_filtered)):
            jj = index_map[j]
            if w[jj] is not None and w[jj] == w[jj]:
                w_filtered[j] = w[jj] / w_median

    # Find piecewise segments
    right, values, dists, gamma = solve_potts_autogamma(y_filtered, w=w_filtered)

    # Extract the steps, mapping indices back etc.
    steps = []
    l = 0
    for r, v, d in zip(right, values, dists):
        steps.append((index_map[l],
                     index_map[r - 1] + 1,
                     v,
                     min(y_filtered[l:r]),
                     abs(d / (r - l))))
        l = r
    return steps


def detect_regressions(steps, threshold=0, min_size=2):
    """Detect regressions in a (noisy) signal.

    A regression means an upward step in the signal.  The value
    'before' a regression is the value immediately preceding the
    upward step.  The value 'after' a regression is the minimum of
    values after the upward step.

    Parameters
    ----------
    steps : list of (left, right, value, min, error)
        List of steps computed by detect_steps, or equivalent
    threshold : float
        Relative threshold for reporting regressions. Filter out jumps
        whose relative size is smaller than threshold, if they are not
        necessary to explain the difference between the best and the latest
        values.
    min_size : int
        Minimum number of commits in a regression to consider it.

    Returns
    -------
    latest_value
        Latest value
    best_value
        Best value
    regression_pos : list of (before, after, value_before, best_value_after)
        List of positions between which the value increased. The first item
        corresponds to the last position at which the best value was obtained.
        The last item indicates the best value found after the regression
        (which is not always the value immediately following the regression).

    """
    if not steps:
        # No data: no regressions
        return None, None, None

    regression_pos = []

    last_v = steps[-1][2]
    best_v = last_v
    thresholded_best_v = last_v
    thresholded_best_err = steps[-1][4]
    prev_l = None
    short_prev = None

    # Find upward steps that resulted to worsened value afterward
    for l, r, cur_v, cur_min, cur_err in reversed(steps):
        threshold_step = max(cur_err, thresholded_best_err, threshold * cur_v)

        if thresholded_best_v > cur_v + threshold_step:
            if r - l < min_size:
                # Accept short intervals conditionally
                short_prev = (thresholded_best_v, thresholded_best_err)

            regression_pos.append((r - 1, prev_l, cur_v, best_v))

            thresholded_best_v = cur_v
            thresholded_best_err = cur_err
        elif short_prev is not None:
            # Ignore the previous short interval, if the level
            # is now back to where it was
            if short_prev[0] <= cur_v + threshold_step:
                regression_pos.pop()
                thresholded_best_v, thresholded_best_err = short_prev
            short_prev = None

        prev_l = l

        if cur_v < best_v:
            best_v = cur_v

    regression_pos.reverse()

    # Return results
    if regression_pos:
        return (last_v, best_v, regression_pos)
    else:
        return (None, None, None)


#
# Fitting piecewise constant functions to noisy data
#

def solve_potts(y, w, gamma, min_size=1, max_size=None,
                min_pos=None, max_pos=None, mu_dist=None):
    """Fit penalized stepwise constant function (Potts model) to data.

    Given a time series y = {y_1, ..., y_n}, fit series x = {x_1, ..., x_n}
    by minimizing the cost functional::

        F[x] = gamma * J(x) + sum(|y - x|**p)

    where J(x) is the number of jumps (x_{j+1} != x_j) in x.

    The algorithm used is described in Ref. [1]_, it uses dynamic
    programming to find an exact solution to the problem (within the
    constraints specified).

    Computation work is ~ O(n**2 log n).

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

    if len(y) == 0:
        return [], [], []

    if min_pos is None:
        min_pos = 0

    if len(y) != len(w):
        raise ValueError("y and w must have same size")

    if max_pos is None:
        max_pos = len(y)

    if mu_dist is None:
        mu_dist = get_mu_dist(y, w)

    if max_size is None:
        max_size = len(y)

    mu, dist = mu_dist.mu, mu_dist.dist

    if min_size >= max_pos - min_pos:
        return [len(y)], [mu(0, len(y) - 1)], [dist(0, len(y) - 1)]

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

        B = [-gamma] * (i1 - i0 + 1)
        p = [0] * (i1 - i0)
        for r in range(i0, i1):
            B[r + 1 - i0] = math.inf
            a = max(r + 1 - max_size, i0)
            b = max(r + 1 - min_size + 1, i0)
            for l in range(a, b):
                b = B[l - i0] + gamma + dist(l, r)
                if b <= B[r + 1 - i0]:
                    B[r + 1 - i0] = b
                    p[r - i0] = l - 1

            mu_dist.cleanup_cache()

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


def solve_potts_autogamma(y, w, beta=None, **kw):
    """Solve Potts problem with automatically determined gamma.

    The optimal value is determined by minimizing the information measure::

        f(gamma) = beta J(x(gamma)) + log sum(abs(x(gamma) - y)**p)

    where x(gamma) is the solution to the Potts problem for a fixed
    gamma. The minimization is only performed rather roughly.

    Parameters
    ----------
    beta : float or 'bic'
         Penalty parameter. Default is 4*ln(n)/n, similar to Bayesian
         information criterion for gaussian model with unknown variance
         assuming 4 DOF per breakpoint.

    """
    n = len(y)

    if n == 0:
        return [], [], [], None

    mu_dist = get_mu_dist(y, w)
    dist = mu_dist.dist

    if beta is None:
        beta = 4 * math.log(n) / n

    gamma_0 = dist(0, n - 1)

    if gamma_0 == 0:
        # Zero variance
        gamma_0 = 1.0

    best_r = [None]
    best_v = [None]
    best_d = [None]
    best_obj = [math.inf]
    best_gamma = [None]

    def f(x):
        gamma = gamma_0 * math.exp(x)
        r, v, d = solve_potts_approx(y, w, gamma=gamma, mu_dist=mu_dist, **kw)

        # MLE fit noise correlation
        def sigma_star(rights, values, rho):
            """
            |E_0| + sum_{j>0} |E_j - rho E_{j-1}|
            """
            l = 1
            E_prev = y[0] - values[0]
            s = abs(E_prev) * w[0]
            for r, v in zip(rights, values):
                for yv, wv in zip(y[l:r], w[l:r]):
                    E = yv - v
                    s += abs(E - rho * E_prev) * wv
                    E_prev = E
                l = r
            return s

        rho_best = golden_search(lambda rho: sigma_star(r, v, rho), -1, 1,
                                 xatol=0.05, expand_bounds=True)

        # Measurement noise floor
        if len(v) > 2:
            absdiff = [abs(v[j + 1] - v[j]) for j in range(len(v) - 1)]
            sigma_0 = 0.1 * min(absdiff)
        else:
            absv = [abs(z) for z in v]
            sigma_0 = 0.001 * min(absv)
        sigma_0 = max(1e-300, sigma_0)

        # Objective function
        s = sigma_star(r, v, rho_best)
        obj = beta * len(r) + math.log(sigma_0 + s)

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
    a = math.log(0.1 / n)
    b = 0.0
    golden_search(f, a, b, xatol=abs(a) * 0.1, ftol=0, expand_bounds=True)
    return best_r[0], best_v[0], best_d[0], best_gamma[0]


def solve_potts_approx(y, w, gamma=None, min_size=1, **kw):
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
        mu_dist = get_mu_dist(y, w)
        kw['mu_dist'] = mu_dist

    if gamma is None:
        dist = mu_dist.dist
        gamma = 3 * dist(0, n - 1) * math.log(n) / n

    if min_size < 10:
        max_size = 20
    else:
        max_size = min_size + 50

    right, values, dists = solve_potts(y, w, gamma, min_size=min_size, max_size=max_size, **kw)
    return merge_pieces(gamma, right, values, dists, mu_dist, max_size=max_size)


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
            change = (dist(l, right[j] - 1) -
                      (dist(l, right[j - 1] - 1) + dist(right[j - 1], right[j] - 1) + gamma))
            if change <= min_change:
                min_change = change
                min_change_j = j - 1
            l = right[j - 1]

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
        prev_score = dist(l, right[j - 1] - 1) + dist(right[j - 1], right[j] - 1)
        new_off = 0
        for off in range(-max_size, max_size + 1):
            if right[j - 1] + off - 1 < l or right[j - 1] + off > right[j] - 1 or off == 0:
                continue
            new_score = dist(l, right[j - 1] + off - 1) + dist(right[j - 1] + off, right[j] - 1)
            if new_score < prev_score:
                new_off = off
                prev_score = new_score

        if new_off != 0:
            right[j - 1] += new_off

        l = right[j - 1]

    # Rebuild values and dists lists
    l = 0
    values = []
    dists = []
    for j in range(len(right)):
        dists.append(dist(l, right[j] - 1))
        values.append(mu(l, right[j] - 1))
        l = right[j]

    return right, values, dists


class L1Dist:
    """
    Fast computations for::

        mu(l, r) = median(y[l:r+1], weights=w[l:r+1])
        dist(l, r) = sum(w*abs(x - mu(l, r)) for x, w in zip(y[l:r+1], weights[l:r+1]))

    We do not use here an approach that has asymptotically optimal
    performance; at least O(n**2 * log(n)) would be achievable, whereas
    we have here O(n**3).  The asymptotic performance does not matter
    for solve_potts_approx, which only looks at small windows of the
    data. It is more important to try to optimize the constant
    prefactors, which for Python means minimal code.

    """
    def __init__(self, y, w):
        self.y = y
        self.w = w

        class mu_dict(collections.defaultdict):
            def __missing__(self, a):
                l, r = a
                v = weighted_median(y[l:r + 1], w[l:r + 1])
                self[a] = v
                return v

        mu = mu_dict()

        class dist_dict(collections.defaultdict):
            def __missing__(self, a):
                l, r = a
                m = mu[l, r]
                v = sum(wx * abs(x - m) for x, wx in zip(y[l:r + 1], w[l:r + 1]))
                self[a] = v
                return v

        self.mu_memo = mu
        self.dist_memo = dist_dict()

    def mu(self, *a):
        return self.mu_memo[a]

    def dist(self, *a):
        return self.dist_memo[a]

    def cleanup_cache(self):
        # Reset cache if it is too big
        if len(self.mu_memo) < 500000:
            return

        self.mu_memo.clear()
        self.dist_memo.clear()


def get_mu_dist(y, w):
    if _rangemedian is not None:
        return _rangemedian.RangeMedian(y, w)
    else:
        return L1Dist(y, w)


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
            v = next(s)
            min_heap_sum += v
            v = -heapq.heappushpop(min_heap, -v)
            min_heap_sum -= v
            heapq.heappush(max_heap, v)
            max_heap_sum += v
            # Ensure d >= 0 despite rounding error
            d = max(0, max_heap_sum - min_heap_sum - max_heap[0])
            yield (max_heap[0], d)

            # Even
            v = next(s)
            max_heap_sum += v
            v = heapq.heappushpop(max_heap, v)
            max_heap_sum -= v
            heapq.heappush(min_heap, -v)
            min_heap_sum += v
            d = max(0, max_heap_sum - min_heap_sum)
            yield ((max_heap[0] - min_heap[0]) / 2, d)
    except StopIteration:
        return


def weighted_median(y, w):
    """
    Compute weighted median of `y` with weights `w`.
    """
    items = sorted(zip(y, w))
    midpoint = sum(w) / 2

    yvals = []
    wsum = 0

    for yy, ww in items:
        wsum += ww
        if wsum > midpoint:
            yvals.append(yy)
            break
        elif wsum == midpoint:
            yvals.append(yy)
    else:
        yvals = y

    return sum(yvals) / len(yvals)


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
        x0 = (ratio * a - (1 - ratio) * b) / (2 * ratio - 1)
        x3 = (ratio * b - (1 - ratio) * a) / (2 * ratio - 1)

    x1 = ratio * x0 + (1 - ratio) * x3
    x2 = (1 - ratio) * x0 + ratio * x3

    f1 = f(x1)
    f2 = f(x2)

    f0 = max(abs(f1), abs(f2))

    while True:
        if abs(x0 - x3) < xatol or abs(f1 - f2) < ftol * f0:
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
        plt.plot([l, r - 1], [v, v], 'b-o', hold=1)
        l = r
