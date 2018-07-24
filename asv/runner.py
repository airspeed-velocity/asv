# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import re
import sys
import shutil
import tempfile
import itertools
import datetime
import pstats

import six

from .console import log, truncate_left
from . import util
from . import statistics


WIN = (os.name == "nt")


# Can't use benchmark.__file__, because that points to the compiled
# file, so it can't be run by another version of Python.
BENCHMARK_RUN_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "benchmark.py")


class BenchmarkRunner(object):
    """
    Control and plan running of a set of benchmarks.

    Takes care of:

    - setup_cache
    - distributing benchmarks to multiple processes
    - launching benchmarks
    - logging messages and displaying results

    The `plan` method generates a sequence of Job objects,
    which the `run` method then runs.
    """

    def __init__(self, benchmarks, benchmark_dir, show_stderr=False, quick=False,
                 profile=False, extra_params=None, selected_idx=None):
        """
        Initialize BenchmarkRunner.

        Parameters
        ----------
        benchmarks : dict, {benchmark_name: Benchmark}
            Set of benchmarks to run.
        benchmark_dir : str
            Root directory for the benchmark suite.
        show_stderr : bool
            Whether to dump output stream from benchmark program.
        quick : bool
            Whether to force a 'quick' run.

        """
        self.benchmarks = benchmarks
        self.benchmark_dir = benchmark_dir
        self.show_stderr = show_stderr
        self.quick = quick
        self.profile = profile
        if extra_params is None:
            self.extra_params = {}
        else:
            self.extra_params = dict(extra_params)
        if selected_idx is None:
            selected_idx = {}
        else:
            self.selected_idx = selected_idx

        if quick:
            self.extra_params['number'] = 1
            self.extra_params['repeat'] = 1
            self.extra_params['warmup_time'] = 0
            self.extra_params['processes'] = 1

    def plan(self):
        # Find all setup_cache routines needed
        setup_caches = {}
        setup_cache_timeout = {}

        for name, benchmark in self.benchmarks:
            key = benchmark.get('setup_cache_key')
            setup_cache_timeout[key] = max(benchmark.get('setup_cache_timeout',
                                                         benchmark['timeout']),
                                           setup_cache_timeout.get(key, 0))

        # Interleave benchmark runs, in setup_cache order
        jobs = []

        insert_stack = []
        benchmark_order = {}
        cache_users = {}
        setup_cache_jobs = {None: None}
        prev_runs = {}

        for name, benchmark in self.benchmarks:
            key = benchmark.get('setup_cache_key')
            benchmark_order.setdefault(key, []).append((name, benchmark))

        for setup_cache_key, benchmark_set in six.iteritems(benchmark_order):
            for name, benchmark in benchmark_set:
                if 'processes' in self.extra_params:
                    processes = int(self.extra_params['processes'])
                else:
                    processes = int(benchmark.get('processes', 1))
                insert_stack.append((name, benchmark, processes, setup_cache_key))
                cache_users.setdefault(setup_cache_key, []).append(name)

        while insert_stack:
            name, benchmark, processes, setup_cache_key = insert_stack.pop(0)

            # Setup cache first, if needed
            if setup_cache_key is None:
                setup_cache_job = None
            elif setup_cache_key in setup_cache_jobs:
                setup_cache_job = setup_cache_jobs[setup_cache_key]
            else:
                setup_cache_job = SetupCacheJob(self.benchmark_dir,
                                                name,
                                                setup_cache_key,
                                                setup_cache_timeout[setup_cache_key])
                setup_cache_jobs[setup_cache_key] = setup_cache_job
                jobs.append(setup_cache_job)

            # Run benchmark
            prev_job = prev_runs.get(name, None)
            job = LaunchBenchmarkJob(name, benchmark, self.benchmark_dir,
                                     self.profile, self.extra_params,
                                     cache_job=setup_cache_job, prev_job=prev_job,
                                     partial=(processes > 1),
                                     selected_idx=self.selected_idx.get(name))
            prev_runs[name] = job
            jobs.append(job)

            # Interleave remaining runs
            if processes > 1:
                insert_stack.append((name, benchmark, processes - 1, setup_cache_key))

            # Cleanup setup cache, if no users left
            if setup_cache_job is not None and processes == 1:
                cache_users[setup_cache_key].remove(name)
                if not cache_users[setup_cache_key]:
                    # No users of this cache left, perform cleanup
                    job = SetupCacheCleanupJob(setup_cache_job)
                    jobs.append(job)
                    del cache_users[setup_cache_key]

        return jobs

    def run(self, jobs, env):
        times = {}

        name_max_width = max(16, util.get_terminal_width() - 33)
        partial_info_printed = False

        try:
            with log.indent():
                for job in jobs:
                    log.step()

                    short_name = truncate_left(job.name, name_max_width)

                    if isinstance(job, SetupCacheJob):
                        partial_info_printed = False
                        self._log_initial("Setting up {0}".format(short_name))
                        job.run(env)
                        self._log_cache_result(job)
                    elif isinstance(job, LaunchBenchmarkJob):
                        if job.partial:
                            if partial_info_printed:
                                log.add(".")
                            else:
                                self._log_initial('Running benchmarks...')
                            partial_info_printed = True
                        else:
                            self._log_initial('{0}'.format(short_name))
                            partial_info_printed = False
                        job.run(env)
                        self._log_benchmark_result(job)
                        if job.result is not None:
                            times[job.name] = job.result
                    else:
                        partial_info_printed = False
                        self._log_initial("Cleaning up {0}".format(short_name))
                        job.run(env)
                        self._log_cache_result(job)
        finally:
            for job in jobs:
                if isinstance(job, SetupCacheCleanupJob):
                    job.run(env)

        return times

    def _log_initial(self, msg):
        self._initial_message = msg
        log.info(msg)

    def _log_result(self, msg):
        assert self._initial_message is not None
        padding_length = util.get_terminal_width() - len(self._initial_message) - 14 - 1 - len(msg)
        self._initial_message = None
        if WIN:
            padding_length -= 1
        padding = " "*padding_length
        log.add(" {0}{1}".format(padding, msg))

    def _log_cache_result(self, item):
        pass

    def _log_benchmark_result(self, job):
        if job.partial:
            return

        # Display status
        if job.failure_count > 0:
            if job.bad_output is None:
                if job.failure_count == job.total_count:
                    self._log_result("failed")
                else:
                    self._log_result("{0}/{1} failed".format(job.failure_count,
                                                             job.total_count))
            else:
                self._log_result("invalid output")
                with log.indent():
                    log.debug(job.bad_output)

        # Display results
        if job.benchmark['params'] and self.show_stderr:
            # Long format display
            if job.failure_count == 0:
                self._log_result("ok")

            display_result = [(v, statistics.get_err(v, s) if s is not None else None)
                              for v, s in zip(job.result['result'], job.result['stats'])]
            display = _format_benchmark_result(display_result, job.benchmark)
            log.info("\n" + "\n".join(display))
        else:
            if job.failure_count == 0:
                # Failure already shown above
                if not job.result['result']:
                    display = "[]"
                else:
                    if job.result['stats'][0]:
                        err = statistics.get_err(job.result['result'][0], job.result['stats'][0])
                    else:
                        err = None
                    display = util.human_value(job.result['result'][0], job.benchmark['unit'], err=err)
                    if len(job.result['result']) > 1:
                        display += ";..."
                self._log_result(display)

        # Dump program output
        if self.show_stderr and job.result.get('stderr'):
            with log.indent():
                log.error(job.result['stderr'])


class LaunchBenchmarkJob(object):
    """
    Job launching a benchmarking process and parsing its results.

    Attributes
    ----------
    result : dict
        Present after completing the job (successfully or unsuccessfully).
        A dictionary with the following keys:

        - `result`: List of numeric values of the benchmarks (one for each parameter
          combination), either returned directly or obtained from `samples` via 
          statistical analysis.

          Values are `None` if benchmark failed or NaN if it was skipped.

          If benchmark is not parameterized, the list contains a single number.

        - `params`: Same as `benchmark['params']`. Empty list if non-parameterized.

        - `samples`: List of lists of sampled raw data points, if benchmark produces
          those and was successful.

        - `stats`: List of results of statistical analysis of data.

        - `profile`: If `profile` is `True` and run was at least partially successful, 
          this key will be a byte string containing the cProfile data. Otherwise, None.

        - `stderr`: Output produced.

        - `errcode`: Error return code.
    """

    def __init__(self, name, benchmark, benchmark_dir, profile=False, extra_params=None,
                 cache_job=None, prev_job=None, partial=False, selected_idx=None):
        """
        Parameters
        ----------
        name : str
            Name of the benchmark

        benchmark : Benchmark object

        benchmark_dir : str
            Path to benchmark directory in which to find the benchmark

        profile : bool
            When `True`, run the benchmark through the `cProfile` profiler
            and save the results.

        extra_params : dict, optional
            Benchmark attribute overrides.

        cache_job : SetupCacheJob, optional
            Job that sets up the required setup cache

        prev_job : LaunchBenchmarkJob, optional
            Previous job for this benchmark, whose result to combine

        partial : bool, optional
            Whether this is the final run for this benchmark, or intermediate one.

        selected_idx : list of int, optional
            Which items to run in a parametrized bencmark.

        """
        self.name = name
        self.benchmark = benchmark
        self.benchmark_dir = benchmark_dir
        self.profile = profile
        self.extra_params = extra_params if extra_params is not None else {}
        self.cache_job = cache_job
        self.prev_job = prev_job
        self.partial = partial
        self.selected_idx = selected_idx

        self.result = None
        self.bad_output = None
        self.failure_count = 0
        self.total_count = 0

    def __repr__(self):
        return "<asv.runner.LaunchBenchmarkJob '{}' at 0x{:x}>".format(self.name, id(self))

    def run(self, env):
        if self.cache_job is not None and self.cache_job.cache_dir is None:
            # Our setup_cache failed, so skip this job
            timestamp = datetime.datetime.utcnow()
            self.result = {'result': None,
                           'samples': None,
                           'stats': None,
                           'params': [],
                           'stderr': self.cache_job.stderr,
                           'started_at': timestamp,
                           'ended_at': timestamp}
            return

        if self.prev_job is not None and self.prev_job.result['result'] is None:
            # Previous job in a multi-process benchmark failed, so skip this job
            self.result = self.prev_job.result
            return

        result = {"stderr": "", "errcode": 0}

        extra_params = dict(self.extra_params)

        if self.benchmark['params']:
            param_iter = enumerate(itertools.product(*self.benchmark['params']))
        else:
            param_iter = [(None, None)]

        self.bad_output = None

        result['started_at'] = datetime.datetime.utcnow()

        bench_results = []
        bench_profiles = []

        for param_idx, params in param_iter:
            if (self.selected_idx is not None and
                    self.benchmark['params'] and
                    param_idx not in self.selected_idx):
                # Use NaN to mark the result as skipped
                bench_results.append(dict(samples=None, result=float('nan'),
                                          stats=None))
                bench_profiles.append(None)
                continue

            if self.prev_job:
                idx = param_idx
                if idx is None:
                    idx = 0
                prev_stats = self.prev_job.result['stats'][idx]
                if prev_stats is not None:
                    extra_params['number'] = prev_stats['number']
                prev_samples = self.prev_job.result['samples'][idx]
            else:
                prev_samples = None

            if self.cache_job is None:
                cwd = tempfile.mkdtemp()
            else:
                cwd = self.cache_job.cache_dir

            try:
                success, data, profile_data, err, out, errcode = \
                    run_benchmark_single(
                        self.benchmark, self.benchmark_dir, env, param_idx,
                        extra_params=extra_params, profile=self.profile,
                        cwd=cwd)
            finally:
                if self.cache_job is None:
                    shutil.rmtree(cwd, True)

            self.total_count += 1
            if success:
                if isinstance(data, dict) and 'samples' in data:
                    if prev_samples is not None:
                        # Combine samples
                        data['samples'] = prev_samples + data['samples']

                    value, stats = statistics.compute_stats(data['samples'],
                                                            data['number'])
                    result_data = dict(samples=data['samples'],
                                       result=value,
                                       stats=stats)
                else:
                    result_data = dict(samples=None,
                                       result=data,
                                       stats=None)

                bench_results.append(result_data)
                if self.profile:
                    bench_profiles.append(profile_data)
            else:
                self.failure_count += 1
                bench_results.append(dict(samples=None, result=None, stats=None))
                bench_profiles.append(None)
                if data is not None:
                    self.bad_output = data

            err = err.strip()
            out = out.strip()

            if errcode:
                if errcode == util.TIMEOUT_RETCODE:
                    if err:
                        err += "\n\n"
                    err += "asv: benchmark timed out (timeout {0}s)\n".format(self.benchmark['timeout'])
                result['errcode'] = errcode

            if err or out:
                err += out
                if self.benchmark['params']:
                    head_msg = "\n\nFor parameters: %s\n" % (", ".join(params),)
                else:
                    head_msg = ''

                result['stderr'] += head_msg
                result['stderr'] += err

        # Produce result
        for key in ['samples', 'result', 'stats']:
            result[key] = [x[key] for x in bench_results]

        if self.benchmark['params']:
            result['params'] = self.benchmark['params']
        else:
            result['params'] = []

        # Combine profile data
        if self.prev_job and 'profile' in self.prev_job.result:
            bench_profiles.append(self.prev_job.result['profile'])

        profile_data = _combine_profile_data(bench_profiles)
        if profile_data is not None:
            result['profile'] = profile_data

        result['ended_at'] = datetime.datetime.utcnow()

        self.result = result


class SetupCacheJob(object):
    """
    Job for running setup_cache and managing its results.
    """

    def __init__(self, benchmark_dir, benchmark_id, setup_cache_key, timeout):        
        if setup_cache_key is None:
            raise ValueError()

        self.benchmark_dir = benchmark_dir
        self.benchmark_id = benchmark_id
        self.setup_cache_key = setup_cache_key
        self.timeout = timeout

        self.cache_dir = None

    @property
    def name(self):
        name = os.path.split(self.setup_cache_key)
        return name[-1]

    def __repr__(self):
        return "<asv.runner.SetupCacheJob '{}' at 0x{:x}>".format(self.name, id(self))

    def run(self, env):
        cache_dir = tempfile.mkdtemp()

        out, err, errcode = env.run(
            [BENCHMARK_RUN_SCRIPT, 'setup_cache',
             os.path.abspath(self.benchmark_dir),
             self.benchmark_id],
            dots=False, display_error=False,
            return_stderr=True, valid_return_codes=None,
            cwd=cache_dir, timeout=self.timeout)

        if errcode == 0:
            self.stderr = None
            self.cache_dir = cache_dir
        else:
            self.stderr = err
            self.clean()

    def clean(self):
        if self.cache_dir is not None:
            util.long_path_rmtree(self.cache_dir, True)
            self.cache_dir = None


class SetupCacheCleanupJob(object):
    def __init__(self, cache_job):
        self.cache_job = cache_job

    @property
    def name(self):
        return self.cache_job.name

    def __repr__(self):
        return "<asv.runner.SetupCacheCleanupJob '{}' at 0x{:x}>".format(self.name, id(self))

    def run(self, env):
        self.cache_job.clean()


def run_benchmark_single(benchmark, root, env, param_idx, profile, extra_params, cwd):
    """
    Run a benchmark, for single parameter combination index in case it
    is parameterized

    Returns
    -------
    success : bool
        Whether test was successful
    data
        If success, the parsed JSON data. If failure, unparsed json data.
    profile_data
        Collected profiler data
    err
        Stderr content
    out
        Stdout content
    errcode
        Process return value

    """
    name = benchmark['name']
    if param_idx is not None:
        name += '-%d' % (param_idx,)

    if profile:
        profile_fd, profile_path = tempfile.mkstemp()
        os.close(profile_fd)
    else:
        profile_path = 'None'

    result_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        result_file.close()

        success = True
        params_str = json.dumps(extra_params)

        out, err, errcode = env.run(
            [BENCHMARK_RUN_SCRIPT, 'run', os.path.abspath(root),
             name, params_str, profile_path, result_file.name],
            dots=False, timeout=benchmark['timeout'],
            display_error=False, return_stderr=True,
            valid_return_codes=None, cwd=cwd)

        if errcode:
            success = False
            parsed = None
        else:
            with open(result_file.name, 'r') as stream:
                data = stream.read()
            try:
                parsed = json.loads(data)
            except:
                success = False
                parsed = data

        if profile:
            with io.open(profile_path, 'rb') as profile_fd:
                profile_data = profile_fd.read()
            if not profile_data:
                profile_data = None
        else:
            profile_data = None

        return success, parsed, profile_data, err, out, errcode
    finally:
        os.remove(result_file.name)
        if profile:
            os.remove(profile_path)


def _combine_profile_data(datasets):
    """
    Combine a list of profile data to a single profile
    """
    datasets = [data for data in datasets if data is not None]
    if not datasets:
        return None
    elif len(datasets) == 1:
        return datasets[0]

    # Load and combine stats
    stats = None

    while datasets:
        data = datasets.pop(0)

        f = tempfile.NamedTemporaryFile(delete=False)
        try:
            f.write(data)
            f.close()
            if stats is None:
                stats = pstats.Stats(f.name)
            else:
                stats.add(f.name)
        finally:
            os.remove(f.name)

    # Write combined stats out
    f = tempfile.NamedTemporaryFile(delete=False)
    try:
        f.close()
        stats.dump_stats(f.name)
        with open(f.name, 'rb') as fp:
            return fp.read()
    finally:
        os.remove(f.name)


def _format_benchmark_result(result, benchmark, max_width=None):
    """
    Format the result from a parameterized benchmark as an ASCII table
    """
    if not result:
        return ['[]']

    def do_formatting(num_column_params):
        # Fold result to a table
        if num_column_params > 0:
            column_params = benchmark['params'][-num_column_params:]
        else:
            column_params = []

        rows = []
        if column_params:
            row_params = benchmark['params'][:-len(column_params)]
            header = benchmark['param_names'][:len(row_params)]
            column_param_permutations = list(itertools.product(*column_params))
            header += [" / ".join(_format_param_value(value) for value in values)
                       for values in column_param_permutations]
            rows.append(header)
            column_items = len(column_param_permutations)
            name_header = " / ".join(benchmark['param_names'][len(row_params):])
        else:
            column_items = 1
            row_params = benchmark['params']
            name_header = ""
            header = benchmark['param_names']
            rows.append(header)

        for j, values in enumerate(itertools.product(*row_params)):
            row_results = [util.human_value(x[0], benchmark['unit'], err=x[1])
                           for x in result[j*column_items:(j+1)*column_items]]
            row = [_format_param_value(value) for value in values] + row_results
            rows.append(row)

        if name_header:
            display = util.format_text_table(rows, 1,
                                             top_header_text=name_header,
                                             top_header_span_start=len(row_params))
        else:
            display = util.format_text_table(rows, 1)

        return display.splitlines()

    # Determine how many parameters can be fit to columns
    if max_width is None:
        max_width = util.get_terminal_width() * 3//4

    text = do_formatting(0)
    for j in range(1, len(benchmark['params'])):
        new_text = do_formatting(j)
        width = max(len(line) for line in new_text)
        if width < max_width:
            text = new_text
        else:
            break

    return text


def _format_param_value(value_repr):
    """
    Format a parameter value for displaying it as test output. The
    values are string obtained via Python repr.

    """
    regexs = ["^'(.+)'$",
              "^u'(.+)'$",
              "^<class '(.+)'>$"]

    for regex in regexs:
        m = re.match(regex, value_repr)
        if m and m.group(1).strip():
            return m.group(1)

    return value_repr
