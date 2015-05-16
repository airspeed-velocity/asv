# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import math
import heapq
import six


#
# Detecting regressions
#

def detect_regressions(y):
    """
    Detect regressions in a (noisy) signal.

    Parameters
    ----------
    y : list of float, none or nan
        Single benchmark result series, with possible missing data

    Returns
    -------
    last_value
        Last value
    last_err
        Last value error estimate
    best_pos
        Last 'good' position
    best_value
        Best value
    best_err
        Best value error estimate

    """

    y = filter_outliers(y)

    index_map = {}
    y_filtered = []
    for j, x in enumerate(y):
        if x is None or x != x:
            # None or NaN: missing data
            continue
        index_map[len(y_filtered)] = j
        y_filtered.append(x)

    # Find piecewise segments
    p = 1
    right, values, dists, gamma = solve_potts_autogamma(y_filtered, p=p, min_size=2)

    # Find best value and compare to the most recent one
    best_r = None
    best_v = None
    best_err = None
    cur_err = None
    cur_v = None
    prev_r = 0

    for r, v, d in zip(right, values, dists):
        if r - prev_r < 3:
            # disregard too short segments
            prev_r = r
            continue

        cur_v = v
        cur_err = abs(d / (r - prev_r))**(1/p)
        prev_r = r

        if best_v is None or cur_v <= best_v + best_err:
            # Prefer showing newer regressions, so if the minimum
            # position is uncertain due to errors in test results,
            # bias it toward newer results
            best_r = index_map[r-1]
            best_v = cur_v
            best_err = cur_err

    if cur_v is None or best_v is None or cur_v <= best_v + max(cur_err, best_err):
        return None, None, None, None, None
    else:
        return (cur_v, cur_err, best_r, best_v, best_err)


def filter_outliers(y):
    """
    Remove 1-3 points lying outside 2*sigma range, if they are between
    points inside the 2*sigma range
    """

    sum_y = 0
    sum_y2 = 0
    n = 0

    for p in y:
        if p is not None:
            sum_y += p
            sum_y2 += p**2
            n += 1

    if n < 5:
        return y

    mean = sum_y/n
    std = math.sqrt(abs(sum_y2/n - mean**2))

    for j, p in enumerate(y):
        if p is not None and abs(p - mean) > 2*std:
            if ((j < 3 or min(abs(x - mean) for x in y[j-3:j+1] if x is not None) < 2*std) and
                (j > len(y)-3 or min(abs(x - mean) for x in y[j:j+4] if x is not None) < 2*std)):
                y[j] = None
    return y



#
# Fitting piecewise constant functions to noisy data
#

def solve_potts(y, gamma, p=2, min_size=2, max_size=1e99,
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
    mu_dist : MuDist, optional
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
    mu_dist : MuDist
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
        mu_dist = MuDist(y, p)

    mu_dist.precompute(max_size, min_pos, max_pos)
    mu, dist = mu_dist.get_funcs()

    if min_size >= max_pos - min_pos:
        return [len(y)], [mu(0,len(y)-1)], [dist(0,len(y)-1)]

    def find_best_partition(n, gamma, dist):
        """
        Perform the Bellman recursion for the optimal partition.

        Returns
        -------
        p : list, length n
            Set of intervals, represented as follows:
            For interval (inclusive) right edge r in {0, ..., n-1},
            the best (exclusive) left edge is at l=p[r].
            Where intervals overlap, the rightmost one has priority.

        """
        i0 = min_pos
        i1 = max_pos

        B = [-gamma]
        p = [None]*i1
        for r in range(i0, i1):
            B.append(inf)
            a = max(r + 1 - max_size, i0)
            b = max(r + 1 - min_size + 1, i0)
            for l in range(a, b):
                b = B[l-i0] + gamma + dist(l, r)
                if b <= B[r+1-i0]:
                    B[r+1-i0] = b
                    p[r] = l - 1
        return p


    def segmentation_from_partition(n, p, mu, dist):
        """
        Convert interval representation computed by find_best_partition
        to a list of intervals and values.
        """
        i0 = min_pos
        r = len(p) - 1
        l = p[r]
        right = []
        values = []
        dists = []
        while r >= i0:
            right.append(r + 1)
            values.append(mu((l + 1), r))
            dists.append(dist((l + 1), r))
            r = l
            l = p[r]
        right.reverse()
        values.reverse()
        dists.reverse()
        return right, values, dists


    n = len(y)
    p = find_best_partition(n, gamma, dist)
    return segmentation_from_partition(n, p, mu, dist)


def solve_potts_autogamma(y, beta=None, **kw):
    """Solve Potts problem with automatically determined gamma.

    The optimal value is determined by minimizing the information measure::

        f(gamma) = beta J(x(gamma)) + log sum(abs(x(gamma) - y)**p)

    where x(gamma) is the solution to the Potts problem for a fixed
    gamma. The minimization is only performed rather roughly.

    Parameters
    ----------
    beta : float or 'bic'
         Penalty parameter. Default is 3*ln(n)/n, similar to Bayesian
         information criterion for gaussian model with unknown variance
         assuming 3 DOF per breakpoint.

    """
    n = len(y)

    if n == 0:
        return [], [], [], None

    mu_dist = MuDist(y, kw.get('p', 2))
    mu, dist = mu_dist.get_funcs()

    if beta is None:
        beta = 3 * math.log(n) / n

    gamma_0 = dist(0, n-1)

    best_r = [None]
    best_v = [None]
    best_d = [None]
    best_obj = [float('inf')]
    best_gamma = [None]

    def f(x):
        gamma = gamma_0 * math.exp(x)
        r, v, d = solve_potts_approx(y, gamma=gamma, mu_dist=mu_dist, **kw)
        obj = beta*len(r) + math.log(1e-300 + sum(d))
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
        mu_dist = MuDist(y, p=p)
        kw['mu_dist'] = mu_dist

    if gamma is None:
        mu, dist = mu_dist.get_funcs()
        gamma = 3 * dist(0,n-1) * math.log(n) / n

    right, values, dists = solve_potts(y, gamma, p=p, max_size=20, **kw)
    return merge_pieces(gamma, right, values, dists, mu_dist, max_size=20)


def merge_pieces(gamma, right, values, dists, mu_dist, max_size):
    """
    Combine consecutive intervals in Potts model solution, if doing
    that reduces the cost function.
    """
    mu, dist = mu_dist.get_funcs()

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


class MuDist(object):
    """
    Precomputed interval means, medians, 1-norms and 2-norms
    """
    def __init__(self, y, p):
        self.y = y
        self.p = p
        self.mu_memo = {}
        self.dist_memo = {}
        if p not in (1, 2):
            raise ValueError("Invalid norm")
        self._precomputed_2 = False
        self.cum_absy = {}

    def precompute(self, max_size, min_pos, max_pos):
        y = self.y
        if self.p == 1:
            if (min_pos, min_pos+max_size) in self.mu_memo:
                # not a full check, but most of the entries likely
                # were already precalculated
                return

            # Precompute medians
            for j in range(min_pos, max_pos):
                medians = rolling_median(y[j:min(max_pos,(j+(max_size+1)))])
                for p, m in enumerate(medians):
                    if j+p > j+max_size:
                        break
                    self.mu_memo[j,j+p] = m

        elif self.p == 2:
            if self._precomputed_2:
                return

            cum_y = [0]
            cum_y2 = [0]
            s = 0
            s2 = 0
            for x in y:
                s += x
                s2 += x**2
                cum_y.append(s)
                cum_y2.append(s2)

            self.cum_y = cum_y
            self.cum_y2 = cum_y2
            self._precomputed_2 = True

    def get_funcs(self):
        """
        Interval distance and value functions d(l, r), mu(l, r)

        The total work involved in computing all values is O(n)
        for p=2, and O(n^2 log n) for p=1.

        """
        if self.p == 1:
            y = self.y
            cum_absy = self.cum_absy

            @memoize(self.mu_memo)
            def mu(l, r):
                return median(y[l:r+1])

            @memoize(self.dist_memo)
            def dist(l, r):
                m = mu(l, r)
                return sum(abs(x - m) for x in y[l:r+1])

        elif self.p == 2:
            if not self._precomputed_2:
                self.precompute(None, None, None)

            cum_y = self.cum_y
            cum_y2 = self.cum_y2

            def mu(l, r):
                # mean(y[l:r+1])
                return (cum_y[r+1] - cum_y[l]) / (r + 1 - l)

            def dist(l, r):
                # sum((y[l:r+1] - mean(y[l:r+1]))**2)
                #
                # This way to compute it is in principle susceptible
                # to rounding errors, but we have to be O(1) fast here
                return abs(cum_y2[r+1] - cum_y2[l] - (cum_y[r+1] - cum_y[l])**2 / (r + 1 - l))
        else:
            raise ValueError("Invalid value for p")

        return mu, dist


def median(items):
    """Note: modifies the input list!"""
    items.sort()
    k = len(items)//2
    if len(items) % 2 == 0:
        return (items[k] + items[k - 1]) / 2
    else:
        return items[k]


def rolling_median(items):
    """Compute medians of [items[:1], items[:2], items[:3], ...] in O(n log n)"""
    min_heap = []
    max_heap = []
    result = []
    s = iter(items)
    try:
        while True:
            v = -heapq.heappushpop(min_heap, -six.next(s))
            heapq.heappush(max_heap, v)
            result.append(max_heap[0])   # number of elements is odd

            v = heapq.heappushpop(max_heap, six.next(s))
            heapq.heappush(min_heap, -v)
            result.append((max_heap[0] - min_heap[0])/2)   # number of elements is even
    except StopIteration:
        return result


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


def memoize(memo):
    def deco(func):
        def wrapper(*a):
            r = memo.get(a)
            if r is None:
                r = func(*a)
                memo[a] = r
            return r
        return wrapper
    return deco
