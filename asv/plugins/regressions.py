# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import re
import itertools
import datetime
import multiprocessing
import time
import traceback
import six

from six.moves.urllib.parse import urlencode

from ..results import iter_results
from ..console import log
from ..publishing import OutputPublisher
from ..step_detect import detect_regressions

from .. import util
from .. import feed


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
        cls._save_feed(conf, benchmarks, regressions, revisions, revision_to_hash)

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
                jumps[k] = (None, jump[1], jump[2], jump[3])

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

    @classmethod
    def _save_feed(cls, conf, benchmarks, data, revisions, revision_to_hash):
        """
        Save the results as an Atom feed
        """

        filename = os.path.join(conf.html_dir, 'regressions.xml')

        # Determine publication date as the date when the benchmark
        # was run --- if it is missing, use the date of the commit
        run_timestamps = {}
        revision_timestamps = {}
        for results in iter_results(conf.results_dir):
            revision = revisions[results.commit_hash]
            revision_timestamps[revision] = results.date

            # Time when the benchmark was run
            for benchmark_name, timestamp in six.iteritems(results.ended_at):
                key = (benchmark_name, revision)
                run_timestamps[key] = timestamp

            # Fallback to commit date
            for benchmark_name in six.iterkeys(results.results):
                key = (benchmark_name, revision)
                run_timestamps.setdefault(key, results.date)

        # Generate feed entries
        entries = []

        for name, graph_path, graph_params, idx, info in data:
            if '(' in name:
                benchmark_name = name[:name.index('(')]
            else:
                benchmark_name = name

            jumps, last_value, best_value = info

            for rev1, rev2, value1, value2 in jumps:
                timestamps = (run_timestamps[benchmark_name, t] for t in (rev1, rev2) if t is not None)
                last_timestamp = max(timestamps)

                updated = datetime.datetime.fromtimestamp(last_timestamp/1000)

                params = dict(graph_params)
                if idx is not None:
                    params['idx'] = idx
                if rev1 is None:
                    params['commits'] = '{0}'.format(revision_to_hash[rev2])
                else:
                    params['commits'] = '{0}-{1}'.format(revision_to_hash[rev1],
                                                         revision_to_hash[rev2])

                link = 'index.html#{0}?{1}'.format(benchmark_name, urlencode(params))

                try:
                    best_percentage = "{0:.2f}%".format(100 * (last_value - best_value) / best_value)
                except ZeroDivisionError:
                    best_percentage = "{0:.2g} units".format(last_value - best_value)

                try:
                    percentage = "{0:.2f}%".format(100 * (value2 - value1) / value1)
                except ZeroDivisionError:
                    percentage = "{0:.2g} units".format(value2 - value1)

                jump_date = datetime.datetime.fromtimestamp(revision_timestamps[rev2]/1000)
                jump_date_str = jump_date.strftime('%Y-%m-%d %H:%M:%S')

                if rev1 is not None:
                    commit_a = revision_to_hash[rev1]
                    commit_b = revision_to_hash[rev2]
                    if 'github.com' in conf.show_commit_url:
                        commit_url = conf.show_commit_url + '../compare/' + commit_a + "..." + commit_b
                    else:
                        commit_url = conf.show_commit_url + commit_a
                    commit_ref = 'in commits <a href="{0}">{1}...{2}</a>'.format(commit_url,
                                                                                 commit_a[:8],
                                                                                 commit_b[:8])
                else:
                    commit_a = revision_to_hash[rev2]
                    commit_url = conf.show_commit_url + commit_a
                    commit_ref = 'in commit <a href="{0}">{1}</a>'.format(commit_url, commit_a[:8])

                unit = benchmarks[benchmark_name].get('unit', '')
                best_value_str = util.human_value(best_value, unit)
                last_value_str = util.human_value(last_value, unit)
                value1_str = util.human_value(value1, unit)
                value2_str = util.human_value(value2, unit)

                title = "{percentage} {name}".format(**locals())
                summary = """
                <a href="{link}">{percentage} regression</a> on {jump_date_str} {commit_ref}.<br>
                New value: {value2_str}, old value: {value1_str}.<br>
                Latest value: {last_value_str} ({best_percentage} worse than best value {best_value_str}).
                """.format(**locals()).strip()

                entries.append(feed.FeedEntry(title, updated, link, summary))

        entries.sort(key=lambda x: x.updated, reverse=True)

        feed.write_atom(filename, entries,
                        title='{0} performance regressions'.format(conf.project),
                        author='Airspeed Velocity',
                        address='{0}.asv'.format(conf.project))


def _analyze_data(graph_data):
    """
    Analyze a single series

    Returns
    -------
    jumps : list of (revision_a, revision_b, prev_value, next_value)
         List of revision pairs, between which there is an upward jump
         in the value, and the preceding and following values.
    cur_value : float
         Most recent value
    best_value : float
         Best value
    """
    try:
        j, entry_name, revisions, values = graph_data

        v, jump_pos, best_v = detect_regressions(values)
        if v is None:
            return j, entry_name, None

        jumps = []
        for jump_r in jump_pos:
            for r in range(jump_r + 1, len(values)):
                if values[r] is not None:
                    next_r = r
                    next_value = values[r]
                    break
            else:
                next_r = jump_r + 1
                next_value = v
            prev_value = values[jump_r]
            jumps.append((revisions[jump_r], revisions[next_r],
                          prev_value, next_value))

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

