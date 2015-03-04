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

            if benchmark['params']:
                for j, param in enumerate(itertools.product(*benchmark['params'])):
                    times = [item[0] for item in graph_data]
                    values = [item[1][j] for item in graph_data]
                    result = cls._analyze_data(times, values)
                    regressions[benchmark_name + '({0})'.format(', '.join(param))] = [j, result]
            else:
                times = [item[0] for item in graph_data]
                values = [item[1] for item in graph_data]
                result = cls._analyze_data(times, values)
                regressions[benchmark_name] = [None, result]

        cls._save(conf, {
            'date_to_hash': date_to_hash,
            'regressions': regressions
        })

    @classmethod
    def _analyze_data(cls, times, values):
        """
        Analyze a single time series
        """
        regressions = detect_regressions(values)
        results = []
        for pos, old_value, new_value in regressions:
            results.append((times[pos], old_value, new_value))
        return results

    @classmethod
    def _save(cls, conf, data):
        fn = os.path.join(conf.html_dir, 'regressions.json')
        util.write_json(fn, data)
