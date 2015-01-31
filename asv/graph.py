# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import itertools

import six
from six.moves import xrange

from . import util


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
        if value is not None:
            if self.summary and hasattr(value, '__len__'):
                value = _mean_with_none(value)
            self.data_points[date].append(value)

    def get_data(self):
        """
        Get the sorted and reduced data.
        """
        def mean(v):
            if not len(v):
                return None
            else:
                if hasattr(v[0], '__len__'):
                    return [_mean_with_none(x[j] for x in v)
                            for j in range(len(v[0]))]
                else:
                    return _mean_with_none(v)

        val = [(k, mean(v)) for (k, v) in
               six.iteritems(self.data_points)]
        val.sort()

        i = 0
        for i in xrange(len(val)):
            if val[i][1] is not None:
                break

        j = i
        for j in xrange(len(val) - 1, i, -1):
            if val[j][1] is not None:
                break

        return val[i:j+1]

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


def _mean_with_none(values):
    """
    Take a mean, with the understanding that None and NaN stand for
    missing data.
    """
    values = [x for x in values if x is not None and x == x]
    if values:
        return sum(values) / float(len(values))
    else:
        return None
