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


JSON_ERROR_RETCODE = -257


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

    def _get_processes(self, benchmark):
        """Get number of processes to use for a job"""
        if 'processes' in self.extra_params:
            return int(self.extra_params['processes'])
        else:
            return int(benchmark.get('processes', 1))

    def plan(self):
        """
        Compute required Job objects

        Yields
        ------
        job : *Job
            A job object to run.
        """
        # Find all setup_cache routines needed
        setup_cache_timeout = {}
        benchmark_order = {}
        cache_users = {}
        max_processes = 0

        for name, benchmark in self.benchmarks:
            key = benchmark.get('setup_cache_key')
            setup_cache_timeout[key] = max(benchmark.get('setup_cache_timeout',
                                                         benchmark['timeout']),
                                           setup_cache_timeout.get(key, 0))
            benchmark_order.setdefault(key, []).append((name, benchmark))
            max_processes = max(max_processes, self._get_processes(benchmark))
            cache_users.setdefault(key, set()).add(name)

        # Interleave benchmark runs, in setup_cache order
        def iter_run_items():
            for run_round in range(max_processes):
                for setup_cache_key, benchmark_set in six.iteritems(benchmark_order):
                    for name, benchmark in benchmark_set:
                        processes = self._get_processes(benchmark)
                        if run_round >= processes:
                            continue
                        is_final = (run_round + 1 >= processes)
                        yield name, benchmark, setup_cache_key, is_final

        # Produce job objects
        setup_cache_jobs = {None: None}
        prev_runs = {}

        for name, benchmark, setup_cache_key, is_final in iter_run_items():
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
                yield setup_cache_job

            # Run benchmark
            prev_job = prev_runs.get(name, None)
            job = LaunchBenchmarkJob(name, benchmark, self.benchmark_dir,
                                     self.profile, self.extra_params,
                                     cache_job=setup_cache_job, prev_job=prev_job,
                                     partial=not is_final,
                                     selected_idx=self.selected_idx.get(name))
            if self._get_processes(benchmark) > 1:
                prev_runs[name] = job
            yield job

            # Cleanup setup cache, if no users left
            if setup_cache_job is not None and is_final:
                cache_users[setup_cache_key].remove(name)
                if not cache_users[setup_cache_key]:
                    # No users of this cache left, perform cleanup
                    yield SetupCacheCleanupJob(setup_cache_job)
                    del setup_cache_jobs[setup_cache_key]
                    del cache_users[setup_cache_key]

        # Cleanup any dangling caches
        for job in setup_cache_jobs.values():
            if job is not None:
                yield SetupCacheCleanupJob(job)

    def run(self, jobs, env):
        times = {}

        name_max_width = max(16, util.get_terminal_width() - 33)
        partial_info_printed = False

        try:
            with log.indent():
                for job in jobs:
                    short_name = truncate_left(job.name, name_max_width)

                    if isinstance(job, SetupCacheJob):
                        partial_info_printed = False
                        log.info("Setting up {0}".format(short_name))
                        job.run(env)
                    elif isinstance(job, LaunchBenchmarkJob):
                        if job.partial:
                            if partial_info_printed:
                                log.add(".")
                            else:
                                log.info('Running benchmarks...')
                            partial_info_printed = True
                        else:
                            log.step()
                            log.info(short_name, reserve_space=True)
                            partial_info_printed = False
                        job.run(env)
                        self._log_benchmark_result(job)
                        if job.result is not None:
                            times[job.name] = job.result
                    else:
                        partial_info_printed = False
                        job.run(env)
        finally:
            for job in jobs:
                if isinstance(job, SetupCacheCleanupJob):
                    job.run(env)

        return times

    def _log_benchmark_result(self, job):
        if job.partial:
            return

        total_count = len(job.result['result'])
        failure_count = sum(r is None for r in job.result['result'])

        # Display status
        if failure_count > 0:
            if failure_count == total_count:
                log.add_padded("failed")
            else:
                log.add_padded("{0}/{1} failed".format(failure_count,
                                                       total_count))

        # Display results
        if job.benchmark['params'] and self.show_stderr:
            # Long format display
            if failure_count == 0:
                log.add_padded("ok")

            display_result = [(v, statistics.get_err(v, s) if s is not None else None)
                              for v, s in zip(job.result['result'], job.result['stats'])]
            display = _format_benchmark_result(display_result, job.benchmark)
            display = "\n".join(display).strip()
            log.info(display, color='default')
        else:
            if failure_count == 0:
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
                log.add_padded(display)

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

        if self.cache_job:
            cache_dir = self.cache_job.cache_dir
        else:
            cache_dir = None

        result = {}
        result['started_at'] = datetime.datetime.utcnow()

        bench_results = []

        if self.benchmark['params']:
            param_iter = enumerate(itertools.product(*self.benchmark['params']))
        else:
            param_iter = [(0, None)]

        for param_idx, params in param_iter:
            if (self.selected_idx is not None and
                    self.benchmark['params'] and
                    param_idx not in self.selected_idx):
                # Use NaN to mark the result as skipped
                bench_results.append(dict(result=util.nan, samples=None,
                                          stats=None, stderr='', errcode=0,
                                          profile=None))
                continue

            cur_extra_params = dict(self.extra_params)

            if self.prev_job:
                prev_stats = self.prev_job.result['stats'][param_idx]
                if prev_stats is not None:
                    cur_extra_params['number'] = prev_stats['number']
                prev_samples = self.prev_job.result['samples'][param_idx]
            else:
                prev_samples = None

            res = run_benchmark_single(
                self.benchmark, self.benchmark_dir, env, param_idx,
                extra_params=cur_extra_params, profile=self.profile,
                cwd=cache_dir)

            if res['samples']:
                # Compute statistics
                samples, number = res['samples']
                if prev_samples is not None:
                    samples = prev_samples + samples
                res['result'], res['stats'] = statistics.compute_stats(samples, number)
                res['samples'] = samples
            else:
                res['stats'] = None

            bench_results.append(res)

        # Produce result
        for key in ['result', 'samples', 'stats']:
            result[key] = [x[key] for x in bench_results]

        stderr = ''
        for item in bench_results:
            if item['stderr']:
                stderr += "\n\n"
                stderr += item['stderr']
        result['stderr'] = stderr.strip()

        if self.benchmark['params']:
            result['params'] = self.benchmark['params']
        else:
            result['params'] = []

        result['errcode'] = 0
        for item in bench_results:
            if item['errcode'] != 0:
                result['errcode'] = item['errcode']

        # Combine profile data
        profile_data = _combine_profile_data([x['profile'] for x in bench_results])
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
            redirect_stderr=True,
            cwd=cache_dir, timeout=self.timeout)

        if errcode == 0:
            self.stderr = None
            self.cache_dir = cache_dir
        else:
            self.stderr = out
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


def run_benchmark_single(benchmark, benchmark_dir, env, param_idx, profile, extra_params, cwd):
    """
    Run a benchmark, for single parameter combination index in case it
    is parameterized

    Parameters
    ----------
    benchmark : dict
        Benchmark object dict
    benchmark_dir : str
        Benchmark directory root
    env : Environment
        Environment to run in
    param_idx : {int, None}
        Parameter index to run benchmark for
    profile : bool
        Whether to run with profile
    extra_params : dict
        Additional parameters to pass to the benchmark
    cwd : {str, None}
        Working directory to run the benchmark in.
        If None, run in a temporary directory.

    Returns
    -------
    result : dict
        Result data. Dictionary with keys

        result : object
            Benchmark result (None indicates failure)
        samples : {([sample, ...], number), None}
            Benchmark measurement samples (or None,
            if not applicable)
        errcode : int
            Process exit code
        stderr : str
            Process stdout/stderr output
        profile : bytes
            Profile data

    success : bool
        Whether test was successful
    data
        If success, the parsed JSON data. If failure, unparsed json data.
    profile_data
        Collected profiler data
    out
        Process output
    errcode
        Process return value

    """
    name = benchmark['name']
    if benchmark['params']:
        name += '-%d' % (param_idx,)

    if profile:
        profile_fd, profile_path = tempfile.mkstemp()
        os.close(profile_fd)
    else:
        profile_path = 'None'

    params_str = json.dumps(extra_params)

    if cwd is None:
        real_cwd = tempfile.mkdtemp()
    else:
        real_cwd = cwd

    result_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        result_file.close()

        out, _, errcode = env.run(
            [BENCHMARK_RUN_SCRIPT, 'run', os.path.abspath(benchmark_dir),
             name, params_str, profile_path, result_file.name],
            dots=False, timeout=benchmark['timeout'],
            display_error=False, return_stderr=True, redirect_stderr=True,
            valid_return_codes=None, cwd=real_cwd)

        result = {}
        result['errcode'] = errcode

        if errcode != 0:
            if errcode == util.TIMEOUT_RETCODE:
                out += "\n\nasv: benchmark timed out (timeout {0}s)\n".format(benchmark['timeout'])

            result['result'] = None
            result['samples'] = None
        else:
            with open(result_file.name, 'r') as stream:
                data = stream.read()

            try:
                data = json.loads(data)
            except ValueError as exc:
                data = None
                result['errcode'] = JSON_ERROR_RETCODE
                out += "\n\nasv: failed to parse benchmark result: {0}\n".format(exc)

            # Special parsing for timing benchmark results
            if isinstance(data, dict) and 'samples' in data and 'number' in data:
                result['result'] = None
                result['samples'] = (data['samples'], data['number'])
            else:
                result['result'] = data
                result['samples'] = None

        out = out.strip()

        if benchmark['params'] and out:
            params, = itertools.islice(itertools.product(*benchmark['params']),
                                       param_idx, param_idx + 1)
            out = "For parameters: {0}\n{1}".format(", ".join(params), out)

        result['stderr'] = out

        if profile:
            with io.open(profile_path, 'rb') as profile_fd:
                profile_data = profile_fd.read()
            result['profile'] = profile_data if profile_data else None
        else:
            result['profile'] = None

        return result
    finally:
        os.remove(result_file.name)
        if profile:
            os.remove(profile_path)
        if cwd is None:
            util.long_path_rmtree(real_cwd, True)


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
