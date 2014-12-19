# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six

from . import util


class Graph(object):
    """
    Manages a single "line" in the resulting plots for the front end.

    Unlike "results", which contain the timings for a single commit,
    these contain the timings for a single benchmark.
    """
    def __init__(self, benchmark_name, params, all_params):
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

        self.path = os.path.join(*parts)

    def add_data_point(self, date, runtime):
        """
        Add a data point to the graph.

        Parameters
        ----------
        date : int
            A Javascript timestamp value representing the time a
            particular commit was merged into the repository.

        runtime : float
            The runtime (in seconds) of the benchmark.
        """
        self.data_points.setdefault(date, [])
        if runtime is not None:
            self.data_points[date].append(runtime)

    def get_data(self):
        """
        Get the sorted and reduced data.
        """
        def mean(v):
            if not len(v):
                return None
            else:
                return sum(v) / float(len(v))

        val = [(k, mean(v)) for (k, v) in
               six.iteritems(self.data_points)]
        val.sort()

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
