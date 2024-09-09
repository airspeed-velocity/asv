Step Detection
==============

Regression detection in ASV is based on detecting stepwise changes
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

Step detection is a well-studied problem. In this implementation, we mainly
follow a variant of the approach outlined in
:cite:p:`sdm-friedrichComplexityPenalizedMEstimation2008` and elsewhere. This
provides a fast algorithm for solving the piecewise weighted fitting problem

.. math::
   :label: gamma-opt

   \mathop{\mathrm{argmin}}_{k,\{j\},\{\mu\}} \gamma k +
   \sum_{r=1}^k\sum_{i=j_{r-1}}^{j_r} w_i |y_i - \mu_r|

The differences are: as we do not need exact solutions, we add additional
heuristics to work around the :math:`{\mathcal O}(n^2)` scaling, which is too
harsh for pure-Python code. For details, see
:py:func:`asv.step_detect.solve_potts_approx`.  Moreover, we follow a slightly
different approach on obtaining a suitable number of intervals, by selecting an
optimal value for :math:`\gamma`, based on a variant of the information
criterion problem discussed in
:cite:p:`sdm-yaoEstimatingNumberChangepoints1988`.


Bayesian information
--------------------

To proceed, we need an argument by which to select a suitable :math:`\gamma` in
:eq:`gamma-opt`. Some of the literature on step detection, e.g.
:cite:p:`sdm-yaoEstimatingNumberChangepoints1988`, suggests results based on
Schwarz information criteria,

.. math::
   :label: ic-form

   \text{SC} = \frac{m}{2} \ln \sigma^2 + k \ln m = \text{min!}

where :math:`\sigma^2` is maximum likelihood variance estimator (if
noise is gaussian). For the implementation, see
:py:func:`asv.step_detect.solve_potts_autogamma`.

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

According to :cite:p:`sdm-friedrichComplexityPenalizedMEstimation2008`, problem :eq:`bic-form` can be solved in
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

References
----------

.. bibliography::
   :filter: docname in docnames
   :labelprefix: SDM_
   :keyprefix: sdm-
