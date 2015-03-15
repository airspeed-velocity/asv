# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import re
import itertools
import six

from ..console import log
from ..publishing import OutputPublisher
from ..results import compatible_results
from ..step_detect import detect_regressions

from .. import util


class Regressions(OutputPublisher):
    name = "regressions"
    button_label = "Show regressions"
    description = "Display information about recent regressions"

    @classmethod
    def publish(cls, conf, repo, benchmarks, graphs, hash_to_date):
        # Analyze the data in the graphs --- it's been cleaned up and
        # it's easier to work with than the results directly

        regressions = []
        seen = {}
        date_to_hash = dict((d, h) for h, d in six.iteritems(hash_to_date))

        data_filter = _GraphDataFilter(conf, repo, hash_to_date)

        all_params = {}
        for graph in six.itervalues(graphs):
            for key, value in six.iteritems(graph.params):
                all_params.setdefault(key, set())
                if value:
                    all_params[key].add(value)

        for file_name, graph in six.iteritems(graphs):
            if 'summary' in graph.params:
                continue
            log.add('.')

            benchmark_name = os.path.basename(file_name)
            benchmark = benchmarks.get(benchmark_name)
            if not benchmark:
                continue

            graph_data = data_filter.get_graph_data(graph, benchmark)

            for j, entry_name, times, values in graph_data:
                result = cls._analyze_data(times, values)
                if result is None:
                    continue

                # Check if range is a single commit
                commit_a = date_to_hash[result[0]]
                commit_b = date_to_hash[result[1]]
                spec = repo.get_range_spec(commit_a, commit_b)
                commits = repo.get_hashes_from_range(spec)
                if len(commits) == 1:
                    commit_a = None

                # Select unique graph params
                graph_params = {}
                for name, value in six.iteritems(graph.params):
                    if len(all_params[name]) > 1:
                        graph_params[name] = value

                graph_path = graph.path + '.json'

                # Produce output -- report only one result for each
                # benchmark for each branch
                regression = [entry_name, graph_path, graph_params, j, result]
                key = (entry_name, graph_params.get('branch'))
                if key not in seen:
                    regressions.append(regression)
                    seen[key] = regression
                else:
                    # Pick the worse regression
                    old_regression = seen[key]
                    prev_result = old_regression[-1]
                    if abs(prev_result[1]*result[2]) < abs(result[1]*prev_result[2]):
                        old_regression[:] = regression

        cls._save(conf, {'regressions': regressions})

    @classmethod
    def _analyze_data(cls, times, values):
        """
        Analyze a single time series

        Returns
        -------
        time_a : int
             Timestamp of last 'good' commit
        time_b : int
             Timestamp of first 'bad' commit
        cur_value : int
             Most recent value
        best_value : int
             Best value
        """
        v, err, best_r, best_v, best_err = detect_regressions(values)
        if v is None:
            return None

        for r in range(best_r + 1, len(values)):
            if values[r] is not None:
                bad_r = r
                break
        else:
            bad_r = best_r + 1

        return times[best_r], times[bad_r], v, best_v

    @classmethod
    def _save(cls, conf, data):
        fn = os.path.join(conf.html_dir, 'regressions.json')
        util.write_json(fn, data)


class _GraphDataFilter(object):
    """
    Obtain data sets from graphs, following configuration settings.
    """

    def __init__(self, conf, repo, hash_to_date):
        self.conf = conf
        self.repo = repo
        self.hash_to_date = hash_to_date
        self.time_sets = {}

    def get_graph_data(self, graph, benchmark):
        """
        Iterator over graph data sets

        Yields
        ------
        param_idx
            Flat index to parameter permutations for parameterized benchmarks.
            None if benchmark is not parameterized.
        entry_name
            Name for the data set. If benchmark is non-parameterized, this is the
            benchmark name.
        times
            List of times (ints)
        values
            List of benchmark values (floats or Nones)

        """
        series = graph.get_data()

        if benchmark.get('params'):
            param_iter = enumerate(itertools.product(*benchmark['params']))
        else:
            param_iter = [(None, None)]

        for j, param in param_iter:
            if param is None:
                entry_name = benchmark['name']
            else:
                entry_name = benchmark['name'] + '({0})'.format(', '.join(param))

            time_set = self._get_allowed_times(graph, benchmark, entry_name)

            times = [item[0] for item in series if item[0] in time_set]
            if param is None:
                values = [item[1] for item in series if item[0] in time_set]
            else:
                values = [item[1][j] for item in series if item[0] in time_set]

            yield j, entry_name, times, values

    def _get_allowed_times(self, graph, benchmark, entry_name):
        """
        Compute the set of times allowed by asv.conf.json.

        The decision which commits to include is based on commit
        order, not on commit authoring date
        """
        time_set = set(self.hash_to_date.values())

        for regex, start_commit in six.iteritems(self.conf.regressions_first_commits):
            if re.match(regex, benchmark['name']) or re.match(regex, entry_name):
                if start_commit is None:
                    # Disable regression detection completely
                    return set()

                if self.conf.branches == [None]:
                    key = (start_commit, None)
                else:
                    key = (start_commit, graph.params.get('branch'))

                if key not in self.time_sets:
                    times = set()
                    spec = self.repo.get_new_range_spec(*key)
                    for commit in self.repo.get_hashes_from_range(spec):
                        time = self.hash_to_date.get(commit[:self.conf.hash_length])
                        if time is not None:
                            times.add(time)
                    self.time_sets[key] = times

                time_set = time_set.intersection(self.time_sets[key])

        return time_set
