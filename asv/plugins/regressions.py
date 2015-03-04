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
    def publish(cls, conf, benchmarks, graphs, date_to_hash):
        # Analyze the data in the graphs --- it's been cleaned up and
        # it's easier to work with than the results directly

        regressions = {}

        for file_name, graph in six.iteritems(graphs):
            if 'summary' in graph.params:
                continue
            log.add('.')

            benchmark_name = os.path.basename(file_name)
            benchmark = benchmarks[benchmark_name]
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

                if entry_name not in regressions:
                    regressions[entry_name] = [j, result]
                else:
                    # Pick the worse regression
                    prev_j, prev_result = regressions[entry_name]
                    if abs(prev_result[1]*result[2]) < abs(result[1]*prev_result[2]):
                        regressions[entry_name] = [j, result]

        cls._save(conf, {
            'date_to_hash': date_to_hash,
            'regressions': regressions
        })

    @classmethod
    def _analyze_data(cls, times, values):
        """
        Analyze a single time series
        """
        v, err, best_r, best_v, best_err = detect_regressions(values)
        if v is None:
            return None
        return times[best_r+1], v, best_v

    @classmethod
    def _save(cls, conf, data):
        fn = os.path.join(conf.html_dir, 'regressions.json')
        util.write_json(fn, data)
