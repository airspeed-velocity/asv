# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import six
import itertools

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
    def publish(cls, conf, repo, benchmarks, graphs, date_to_hash):
        # Analyze the data in the graphs --- it's been cleaned up and
        # it's easier to work with than the results directly

        regressions = {}

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
            graph_data = graph.get_data()

            if benchmark.get('params'):
                def iter_data():
                    for j, param in enumerate(itertools.product(*benchmark['params'])):
                        times = [item[0] for item in graph_data]
                        values = [item[1][j] for item in graph_data]
                        entry_name = benchmark_name + '({0})'.format(', '.join(param))
                        yield j, entry_name, times, values
            else:
                def iter_data():
                    times = [item[0] for item in graph_data]
                    values = [item[1] for item in graph_data]
                    yield None, benchmark_name, times, values

            for j, entry_name, times, values in iter_data():
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

                # Produce output
                if entry_name not in regressions:
                    regressions[entry_name] = [graph_params, j, result]
                else:
                    # Pick the worse regression
                    prev_params, prev_j, prev_result = regressions[entry_name]
                    if abs(prev_result[1]*result[2]) < abs(result[1]*prev_result[2]):
                        regressions[entry_name] = [graph_params, j, result]

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
