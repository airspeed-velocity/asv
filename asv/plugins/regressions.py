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

        for j, (file_name, graph) in enumerate(graphs):
            if 'summary' in graph.params:
                continue

            benchmark_name = os.path.basename(file_name)
            benchmark = benchmarks.get(benchmark_name)
            if not benchmark:
                continue

            log.add('.')

            for graph_data in data_filter.get_graph_data(graph, benchmark):
                cls._process_regression(regressions, seen, revision_to_hash, repo, all_params,
                                        graph_data, graph)

        cls._save(conf, {'regressions': regressions})

    @classmethod
    def _process_regression(cls, regressions, seen, revision_to_hash, repo, all_params,
                           graph_data, graph):
        j, entry_name, steps = graph_data

        v, best_v, jumps = detect_regressions(steps)

        if v is None:
            return

        result = (jumps, v, best_v)

        # Check which ranges are a single commit
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


class _GraphDataFilter(object):
    """
    Obtain data sets from graphs, following configuration settings.
    """

    def __init__(self, conf, repo, revisions):
        self.conf = conf
        self.repo = repo
        self.revisions = revisions
        self._start_revisions = {}

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
        steps
            Steps to consider in regression detection.

        """
        if benchmark.get('params'):
            param_iter = enumerate(zip(itertools.product(*benchmark['params']),
                                           graph.get_steps()))
        else:
            param_iter = [(None, (None, graph.get_steps()))]

        for j, (param, steps) in param_iter:
            if param is None:
                entry_name = benchmark['name']
            else:
                entry_name = benchmark['name'] + '({0})'.format(', '.join(param))

            start_revision = self._get_start_revision(graph, benchmark, entry_name)

            if start_revision is None:
                # Skip detection
                continue

            steps = [step for step in steps if step[1] >= start_revision]

            yield j, entry_name, steps

    def _get_start_revision(self, graph, benchmark, entry_name):
        """
        Compute the first revision allowed by asv.conf.json.

        Revisions correspond to linearized commit history and the
        regression detection runs on this order --- the starting commit
        thus corresponds to a specific starting revision.
        """
        start_revision = min(six.itervalues(self.revisions))

        if graph.params.get('branch'):
            branch_suffix = '@' + graph.params.get('branch')
        else:
            branch_suffix = ''

        for regex, start_commit in six.iteritems(self.conf.regressions_first_commits):
            if re.match(regex, entry_name + branch_suffix):
                if start_commit is None:
                    # Disable regression detection completely
                    return None

                if self.conf.branches == [None]:
                    key = (start_commit, None)
                else:
                    key = (start_commit, graph.params.get('branch'))

                if key not in self._start_revisions:
                    spec = self.repo.get_new_range_spec(*key)
                    start_hash = self.repo.get_hash_from_name(start_commit)

                    for commit in [start_hash] + self.repo.get_hashes_from_range(spec):
                        rev = self.revisions.get(commit)
                        if rev is not None:
                            self._start_revisions[key] = rev
                            break
                    else:
                        # Commit not found in the branch --- warn and ignore.
                        log.warn(("Commit {0} specified in `regressions_first_commits` "
                                  "not found in branch").format(start_commit))
                        self._start_revisions[key] = -1

                start_revision = max(start_revision, self._start_revisions[key] + 1)

        return start_revision
