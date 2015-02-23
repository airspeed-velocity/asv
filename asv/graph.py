# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six
from six.moves import xrange

from . import util


# This is the maximum number of points to include in summary graphs.
# It is based on the number of pixels in the summary graph display on
# a recent Retina MacBook Pro (3840 pixels across the screen, divided
# by 5 summaries across, divided by 2 for good measure and to account
# for width of the line).
RESAMPLED_POINTS = (3840 / 5 / 2)


class Graph(object):
    """
    Manages a single "line" in the resulting plots for the front end.

    Unlike "results", which contain the timings for a single commit,
    these contain the timings for a single benchmark.
    """
    def __init__(self, benchmark_name, params, all_params,
                 summary=False):
        """
        Initially the graph contains no data.  It must be added using
        multiple calls to `add_data_point`.

        Parameters
        ----------
        benchmark_name : str
            A unique string to identify the benchmark, and display in
            the frontend.

        params : dict of str -> str
            A dictionary of parameters describing the benchmark.

        all_params : dict of str -> str
            A dictionary of all parameters that were found amongst all
            benchmark results.  This is used to fill in blanks for
            parameters that might not have been recorded for a
            particular result.

        summary : bool, optional
            Whether to generate summary graph, averaged over parameter
            configurations (if test is parametric).

        """
        # Fill in missing parameters
        for key in six.iterkeys(all_params):
            if key not in params:
                params[key] = None

        self.benchmark_name = benchmark_name
        self.params = params
        self.data_points = {}

        # TODO: Make filename safe
        parts = ['graphs']

        l = list(six.iteritems(self.params))
        l.sort()
        for key, val in l:
            if val is None:
                parts.append(key)
            else:
                parts.append('{0}-{1}'.format(key, val))
        parts.append(benchmark_name)

        self.summary = summary
        self.path = os.path.join(*parts)
        self.n_series = None
        self.scalar_series = True

    def add_data_point(self, date, value):
        """
        Add a data point to the graph.

        Parameters
        ----------
        date : int
            A Javascript timestamp value representing the time a
            particular commit was merged into the repository.

        value : float or list
            The value(s) to plot in the benchmark.

        """
        # Add simple time series
        self.data_points.setdefault(date, [])
        if not _is_na(value):
            if not hasattr(value, '__len__'):
                value = [value]
            else:
                self.scalar_series = False

            if self.n_series is None:
                self.n_series = len(value)
            elif len(value) != self.n_series:
                raise ValueError("Mismatching number of data series in graph")

            self.data_points[date].append(value)

    def resample_data(self, val):
        if len(val) < RESAMPLED_POINTS:
            return val

        min_time = min(x[0] for x in val)
        max_time = max(x[0] for x in val)
        step_size = int((max_time - min_time) / RESAMPLED_POINTS)

        new_val = []
        j = 0
        for i in xrange(min_time + step_size, max_time + step_size, step_size):
            chunk = []
            while j < len(val) and val[j][0] < i:
                chunk.append(val[j][1])
                j += 1
            if len(chunk):
                new_val.append((i, _mean_with_none(chunk)))
        return new_val

    def get_data(self):
        """
        Get the sorted and reduced data.
        """

        if self.n_series is None:
            # No non-null data points
            self.n_series = 1

        def mean_axis0(v):
            if not v:
                return [None]*self.n_series
            return [_mean_with_none(x[j] for x in v)
                    for j in xrange(self.n_series)]

        # Average data over dates
        val = [(k, mean_axis0(v)) for (k, v) in
               six.iteritems(self.data_points)]
        val.sort()

        # Discard missing data at edges
        i = 0
        for i in xrange(len(val)):
            if any(not _is_na(v) for v in val[i][1]):
                break
        else:
            i = len(val)

        j = i
        for j in xrange(len(val) - 1, i, -1):
            if any(not _is_na(v) for v in val[j][1]):
                break

        val = val[i:j+1]

        # Reduce data for summary
        if self.summary and self.n_series > 1:
            # Given multiple input series
            #
            #     val = [(x_0, (y[0,0], y[0,1], ..., y[0,n])), 
            #            (x_1, (y[1,0], y[1,1], ..., y[1,n])),
            #            ... ]
            #
            # calculate summary data series
            #
            #     z = geom_mean(y, axis=1)
            #
            # Missing data in y is filled by the previous non-null
            # values (or the first non-null value, for nulls at the
            # beginning), to avoid meaningless jumps in the result.
            # Data points missing from all series are not filled.

            # Find first non-null values
            first_values = [None]*self.n_series
            for k, v in val:
                for j, x in enumerate(v):
                    if first_values[j] is None and not _is_na(x):
                        first_values[j] = x
                if not any(_is_na(x) for x in first_values):
                    break

            first_values = [fv if fv is not None else 1.0 
                            for fv in first_values]

            # Compute geom mean of filled series
            last_values = [None]*self.n_series
            new_val = []
            for k, v in val:
                # Fill missing data, unless it's missing from all
                # parameter combinations
                cur_vals = []
                if any(not _is_na(x) for x in v):
                    for j, x in enumerate(v):
                        if _is_na(x):
                            if last_values[j] is not None:
                                x = last_values[j]
                            else:
                                x = first_values[j]
                        else:
                            last_values[j] = x

                        cur_vals.append(x)

                # Mean of normalized values, on top of mean of means
                v = _geom_mean_with_none(cur_vals)
                new_val.append((k, v))

            val = new_val
        elif self.summary or self.scalar_series:
            # Single-element series
            val = [(k, v[0]) for k, v in val]

        if self.summary:
            # Resample
            val = self.resample_data(val)

        return val

    def save(self, html_dir):
        """
        Save the graph to a .json file used by the frontend.

        Parameters
        ----------
        html_dir : str
            The root of the HTML tree.
        """
        filename = os.path.join(html_dir, self.path + ".json")

        val = self.get_data()

        util.write_json(filename, val)


def _is_na(value):
    """
    Return true if value is None or nan
    """
    return value is None or value != value


def _mean_with_none(values):
    """
    Take a mean, with the understanding that None and NaN stand for
    missing data.
    """
    values = [x for x in values if not _is_na(x)]
    if values:
        return sum(values) / len(values)
    else:
        return None


def _geom_mean_with_none(values):
    """
    Compute geometric mean, with the understanding that None and NaN
    stand for missing data.
    """
    values = [x for x in values if not _is_na(x)]
    if values:
        exponent = 1/len(values)
        prod = 1.0
        acc = 0
        for x in values:
            prod *= abs(x)**exponent
            acc += x
        return prod if acc >= 0 else -prod
    else:
        return None
