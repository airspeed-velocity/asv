# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import re
import itertools
import multiprocessing
import time
import traceback
import six

from ..console import log
from ..publishing import OutputPublisher
from ..step_detect import detect_regressions, detect_steps

from .. import util


class Regressions(OutputPublisher):
    name = "regressions"
    button_label = "Show regressions"
    description = "Display information about recent regressions"

    @classmethod
    def publish(cls, conf, repo, benchmarks, graphs, revisions):
        # Analyze the data in the graphs --- it's been cleaned up and
        # it's easier to work with than the results directly

        regressions = []
        seen = {}
        revision_to_hash = dict((r, h) for h, r in six.iteritems(revisions))

        data_filter = _GraphDataFilter(conf, repo, revisions)

        all_params = graphs.get_params()
        last_percentage_time = time.time()

        n_processes = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(n_processes)
        try:
            results = []
            for j, (file_name, graph) in enumerate(graphs):
                if 'summary' in graph.params:
                    continue

                # Print progress status
                log.add('.')
                if time.time() - last_percentage_time > 5:
                    log.add('{0:.0f}%'.format(100*j/len(graphs)))
                    last_percentage_time = time.time()

                benchmark_name = os.path.basename(file_name)
                benchmark = benchmarks.get(benchmark_name)
                if not benchmark:
                    continue

                graph_data = data_filter.get_graph_data(graph, benchmark)
                for data in graph_data:
                    results.append((pool.apply_async(_analyze_data, (data,), {}), graph))

                while len(results) > n_processes:
                    r, graph = results.pop(0)
                    cls._insert_regression(regressions, seen, revision_to_hash, repo, all_params,
                                           r.get(), graph)

            while results:
                r, graph = results.pop(0)
                cls._insert_regression(regressions, seen, revision_to_hash, repo, all_params,
                                       r.get(), graph)
        finally:
            pool.terminate()

        cls._save(conf, {'regressions': regressions})

    @classmethod
    def _insert_regression(cls, regressions, seen, revision_to_hash, repo, all_params,
                           result_item, graph):
        j, entry_name, result = result_item

        if result is None:
            return

        # Check which ranges are a single commit
        jumps = result[0]
        for k, jump in enumerate(jumps):
            commit_a = revision_to_hash[jump[0]]
            commit_b = revision_to_hash[jump[1]]
            spec = repo.get_range_spec(commit_a, commit_b)
            commits = repo.get_hashes_from_range(spec)
            if len(commits) == 1:
                jumps[k] = (None, jump[1])

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

    @classmethod
    def _save(cls, conf, data):
        fn = os.path.join(conf.html_dir, 'regressions.json')
        util.write_json(fn, data)


def _analyze_data(graph_data):
    """
    Analyze a single series

    Returns
    -------
    jumps : list of (revision_a, revision_b)
         List of revision pairs, between which there is an upward jump
         in the value.
    cur_value : int
         Most recent value
    best_value : int
         Best value
    """
    try:
        j, entry_name, revisions, values = graph_data

        steps = detect_steps(values)
        v, best_v, jump_pos = detect_regressions(steps)
        if v is None:
            return j, entry_name, None

        jumps = []
        for jump_r in jump_pos:
            for r in range(jump_r + 1, len(values)):
                if values[r] is not None:
                    next_r = r
                    break
            else:
                next_r = jump_r + 1
            jumps.append((revisions[jump_r], revisions[next_r]))

        return j, entry_name, (jumps, v, best_v)
    except BaseException as exc:
        raise util.ParallelFailure(str(exc), exc.__class__, traceback.format_exc())


class _GraphDataFilter(object):
    """
    Obtain data sets from graphs, following configuration settings.
    """

    def __init__(self, conf, repo, revisions):
        self.conf = conf
        self.repo = repo
        self.revisions = revisions
        self.revision_sets = {}

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
        revisions
            List of revisions (ints)
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

            revision_set = self._get_allowed_revisions(graph, benchmark, entry_name)

            times = [item[0] for item in series if item[0] in revision_set]
            if param is None:
                values = [item[1] for item in series if item[0] in revision_set]
            else:
                values = [item[1][j] for item in series if item[0] in revision_set]

            yield j, entry_name, times, values

    def _get_allowed_revisions(self, graph, benchmark, entry_name):
        """
        Compute the set of revisions allowed by asv.conf.json.
        """
        revision_set = set(self.revisions.values())

        if graph.params.get('branch'):
            branch_suffix = '@' + graph.params.get('branch')
        else:
            branch_suffix = ''

        for regex, start_commit in six.iteritems(self.conf.regressions_first_commits):
            if re.match(regex, entry_name + branch_suffix):
                if start_commit is None:
                    # Disable regression detection completely
                    return set()

                if self.conf.branches == [None]:
                    key = (start_commit, None)
                else:
                    key = (start_commit, graph.params.get('branch'))

                if key not in self.revision_sets:
                    revs = set()
                    spec = self.repo.get_new_range_spec(*key)
                    start_hash = self.repo.get_hash_from_name(start_commit)
                    for commit in [start_hash] + self.repo.get_hashes_from_range(spec):
                        rev = self.revisions.get(commit)
                        if rev is not None:
                            revs.add(rev)
                    self.revision_sets[key] = revs

                revision_set = revision_set.intersection(self.revision_sets[key])

        return revision_set
