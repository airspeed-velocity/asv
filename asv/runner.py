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
import time
import tempfile
import itertools
import datetime
import pstats

import six

from .console import log, truncate_left
from .results import Results
from . import util
from . import statistics


WIN = (os.name == "nt")


# Can't use benchmark.__file__, because that points to the compiled
# file, so it can't be run by another version of Python.
BENCHMARK_RUN_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "benchmark.py")


JSON_ERROR_RETCODE = -257


BenchmarkResult = util.namedtuple_with_doc(
    'BenchmarkResult',
    ['result', 'samples', 'number', 'errcode', 'stderr', 'profile'],
    """
    Postprocessed benchmark result

    Attributes
    ----------
    result : list of object
        List of numeric values of the benchmarks (one for each parameter
        combination).
        Values are `None` if benchmark failed or NaN if it was skipped.
    samples : list of {list, None}
        List of lists of sampled raw data points (or Nones if
        no sampling done).
    number : list of {dict, None}
        List of actual repeat counts for each sample (or Nones if
        no sampling done).
    errcode : int
        Process exit code
    stderr : str
        Process stdout/stderr output
    profile : bytes
        If `profile` is `True` and run was at least partially successful,
        this key will be a byte string containing the cProfile data.
        Otherwise, None.
    """)


def skip_benchmarks(benchmarks, env, results=None):
    """
    Mark benchmarks as skipped.

    Parameters
    ----------
    benchmarks : Benchmarks
        Set of benchmarks to skip
    env : Environment
        Environment to skip them in
    results : Results, optional
        Where to store the results.
        If omitted, stored to a new unnamed Results object.

    Returns
    -------
    results : Results
        Benchmark results.

    """
    if results is None:
        results = Results.unnamed()

    started_at = datetime.datetime.utcnow()

    log.warn("Skipping {0}".format(env.name))
    with log.indent():
        for name, benchmark in six.iteritems(benchmarks):
            log.step()
            log.warn('{0} skipped'.format(name))

            r = fail_benchmark(benchmark)
            results.add_result(benchmark, r,
                               selected_idx=benchmarks.benchmark_selection.get(name),
                               started_at=started_at,
                               ended_at=datetime.datetime.utcnow())

    return results


def run_benchmarks(benchmarks, env, results=None,
                   show_stderr=False, quick=False, profile=False,
                   extra_params=None,
                   record_samples=False, append_samples=False):
    """
    Run all of the benchmarks in the given `Environment`.

    Parameters
    ----------
    benchmarks : Benchmarks
        Benchmarks to run
    env : Environment object
        Environment in which to run the benchmarks.
    results : Results, optional
        Where to store the results.
        If omitted, stored to a new unnamed Results object.
    show_stderr : bool, optional
        When `True`, display any stderr emitted by the benchmark.
    quick : bool, optional
        When `True`, run each benchmark function exactly once.
        This is useful to quickly find errors in the benchmark
        functions, without taking the time necessary to get
        accurate timings.
    profile : bool, optional
        When `True`, run the benchmark through the `cProfile`
        profiler.
    extra_params : dict, optional
        Override values for benchmark attributes.
    record_samples : bool, optional
        Whether to retain result samples or discard them.
    append_samples : bool, optional
        Whether to retain any previously measured result samples
        and use them in statistics computations.

    Returns
    -------
    results : Results
        Benchmark results.

    """

    if extra_params is None:
        extra_params = {}
    else:
        extra_params = dict(extra_params)

    if quick:
        extra_params['number'] = 1
        extra_params['repeat'] = 1
        extra_params['warmup_time'] = 0
        extra_params['processes'] = 1

    if results is None:
        results = Results.unnamed()

    if append_samples:
        record_samples = True

    # Find all setup_cache routines needed
    setup_cache_timeout = {}
    benchmark_order = {}
    cache_users = {}
    max_processes = 0

    def get_processes(benchmark):
        """Get number of processes to use for a job"""
        if 'processes' in extra_params:
            return int(extra_params['processes'])
        else:
            return int(benchmark.get('processes', 1))

    for name, benchmark in sorted(six.iteritems(benchmarks)):
        key = benchmark.get('setup_cache_key')
        setup_cache_timeout[key] = max(benchmark.get('setup_cache_timeout',
                                                     benchmark['timeout']),
                                       setup_cache_timeout.get(key, 0))
        benchmark_order.setdefault(key, []).append((name, benchmark))
        max_processes = max(max_processes, get_processes(benchmark))
        cache_users.setdefault(key, set()).add(name)

    # Interleave benchmark runs, in setup_cache order
    def iter_run_items():
        for run_round in range(max_processes, 0, -1):
            for setup_cache_key, benchmark_set in six.iteritems(benchmark_order):
                for name, benchmark in benchmark_set:
                    processes = get_processes(benchmark)
                    if run_round > processes:
                        continue
                    is_final = (run_round == 1)
                    yield name, benchmark, setup_cache_key, is_final

    # Run benchmarks in order
    cache_dirs = {None: None}
    failed_benchmarks = set()
    failed_setup_cache = {}

    started_at = datetime.datetime.utcnow()

    if append_samples:
        previous_result_keys = results.get_result_keys(benchmarks)
    else:
        previous_result_keys = set()

    log.info("Benchmarking {0}".format(env.name))

    partial_info_time = None
    indent = log.indent()
    indent.__enter__()

    try:
        for name, benchmark, setup_cache_key, is_final in iter_run_items():
            if is_final:
                log.step()

            selected_idx = benchmarks.benchmark_selection.get(name)

            # Don't try to rerun failed benchmarks
            if name in failed_benchmarks:
                continue

            # Setup cache first, if needed
            if setup_cache_key is None:
                cache_dir = None
            elif setup_cache_key in cache_dirs:
                cache_dir = cache_dirs[setup_cache_key]
            elif setup_cache_key not in failed_setup_cache:
                partial_info_time = None
                short_key = os.path.relpath(setup_cache_key, benchmarks.benchmark_dir)
                log.info("Setting up {0}".format(short_key), reserve_space=True)
                cache_dir, stderr = create_setup_cache(name, benchmarks.benchmark_dir, env,
                                                       setup_cache_timeout[setup_cache_key])
                if cache_dir is not None:
                    log.add_padded('ok')
                    cache_dirs[setup_cache_key] = cache_dir
                else:
                    log.add_padded('failed')
                    if stderr and show_stderr:
                        with log.indent():
                            log.error(stderr)
                    failed_setup_cache[setup_cache_key] = stderr

            if setup_cache_key in failed_setup_cache:
                # Mark benchmark as failed
                partial_info_time = None
                log.warn('{0} skipped (setup_cache failed)'.format(name))
                stderr = 'asv: setup_cache failed\n\n{}'.format(failed_setup_cache[setup_cache_key])
                res = fail_benchmark(benchmark, stderr=stderr)
                results.add_result(benchmark, res,
                                   selected_idx=selected_idx,
                                   started_at=started_at,
                                   ended_at=datetime.datetime.utcnow(),
                                   record_samples=record_samples)
                failed_benchmarks.add(name)
                continue

            # If appending to previous results, make sure to use the
            # same value for 'number' attribute.
            cur_extra_params = extra_params
            if name in previous_result_keys:
                cur_extra_params = []
                prev_stats = results.get_result_stats(name, benchmark['params'])
                for s in prev_stats:
                    if s is None or 'number' not in s:
                        p = extra_params
                    else:
                        p = dict(extra_params)
                        p['number'] = s['number']
                    cur_extra_params.append(p)

            # Run benchmark
            if is_final:
                partial_info_time = None
                log.info(name, reserve_space=True)
            elif partial_info_time is None or time.time() > partial_info_time + 30:
                partial_info_time = time.time()
                log.info('Running ({0}--)'.format(name))

            res = run_benchmark(benchmark, benchmarks.benchmark_dir, env,
                                profile=profile,
                                selected_idx=selected_idx,
                                extra_params=cur_extra_params,
                                cwd=cache_dir)

            # Save result
            results.add_result(benchmark, res,
                               selected_idx=selected_idx,
                               started_at=started_at,
                               ended_at=datetime.datetime.utcnow(),
                               record_samples=(not is_final or record_samples),
                               append_samples=(name in previous_result_keys))

            previous_result_keys.add(name)

            if all(r is None for r in res.result):
                failed_benchmarks.add(name)

            # Log result
            if is_final or name in failed_benchmarks:
                partial_info_time = None
                if not is_final:
                    log.info(name, reserve_space=True)
                log_benchmark_result(benchmark, results,
                                     show_stderr=show_stderr)
            else:
                log.add('.')

            # Cleanup setup cache, if no users left
            if cache_dir is not None and is_final:
                cache_users[setup_cache_key].remove(name)
                if not cache_users[setup_cache_key]:
                    # No users of this cache left, perform cleanup
                    util.long_path_rmtree(cache_dir, True)
                    del cache_dirs[setup_cache_key]
    finally:
        # Cleanup any dangling caches
        for cache_dir in cache_dirs.values():
            if cache_dir is not None:
                util.long_path_rmtree(cache_dir, True)
        indent.__exit__(None, None, None)

    return results


def log_benchmark_result(benchmark, results, show_stderr=False):
    name = benchmark['name']

    result = results.get_result_value(name, benchmark['params'])
    stats = results.get_result_stats(name, benchmark['params'])

    total_count = len(result)
    failure_count = sum(r is None for r in result)

    # Display status
    if failure_count > 0:
        if failure_count == total_count:
            log.add_padded("failed")
        else:
            log.add_padded("{0}/{1} failed".format(failure_count,
                                                   total_count))

    # Display results
    if benchmark['params']:
        # Long format display
        if failure_count == 0:
            log.add_padded("ok")

        display_result = [(v, statistics.get_err(v, s) if s is not None else None)
                          for v, s in zip(result, stats)]
        display = _format_benchmark_result(display_result, benchmark)
        display = "\n".join(display).strip()
        log.info(display, color='default')
    else:
        if failure_count == 0:
            # Failure already shown above
            if not result:
                display = "[]"
            else:
                if stats[0]:
                    err = statistics.get_err(result[0], stats[0])
                else:
                    err = None
                display = util.human_value(result[0], benchmark['unit'], err=err)
                if len(result) > 1:
                    display += ";..."
            log.add_padded(display)

    # Dump program output
    stderr = results.stderr.get(name)
    if stderr and show_stderr:
        with log.indent():
            log.error(stderr)


def create_setup_cache(benchmark_id, benchmark_dir, env, timeout):
    cache_dir = tempfile.mkdtemp()

    out, _, errcode = env.run(
        [BENCHMARK_RUN_SCRIPT, 'setup_cache',
         os.path.abspath(benchmark_dir),
         benchmark_id],
        dots=False, display_error=False,
        return_stderr=True, valid_return_codes=None,
        redirect_stderr=True,
        cwd=cache_dir, timeout=timeout)

    if errcode == 0:
        return cache_dir, None
    else:
        util.long_path_rmtree(cache_dir, True)
        return None, out.strip()


def fail_benchmark(benchmark, stderr='', errcode=1):
    """
    Return a BenchmarkResult describing a failed benchmark.
    """
    if benchmark['params']:
        # Mark only selected parameter combinations skipped
        params = itertools.product(*benchmark['params'])
        result = [None for idx in params]
        samples = [None] * len(result)
        number = [None] * len(result)
    else:
        result = [None]
        samples = [None]
        number = [None]

    return BenchmarkResult(result=result,
                           samples=samples,
                           number=number,
                           errcode=errcode,
                           stderr=stderr,
                           profile=None)


def run_benchmark(benchmark, benchmark_dir, env, profile,
                  selected_idx=None,
                  extra_params=None,
                  cwd=None,
                  prev_result=None):
    """
    Run a benchmark.

    Parameters
    ----------
    benchmark : dict
        Benchmark object dict
    benchmark_dir : str
        Benchmark directory root
    env : Environment
        Environment to run in
    profile : bool
        Whether to run with profile
    selected_idx : set, optional
        Set of parameter indices to run for.
    extra_params : {dict, list}, optional
        Additional parameters to pass to the benchmark.
        If a list, each entry should correspond to a benchmark
        parameter combination.
    cwd : str, optional
        Working directory to run the benchmark in.
        If None, run in a temporary directory.

    Returns
    -------
    result : BenchmarkResult
        Result data.

    """

    if extra_params is None:
        extra_params = {}

    result = []
    samples = []
    number = []
    profiles = []
    stderr = ''
    errcode = 0

    if benchmark['params']:
        param_iter = enumerate(itertools.product(*benchmark['params']))
    else:
        param_iter = [(0, None)]

    for param_idx, params in param_iter:
        if selected_idx is not None and param_idx not in selected_idx:
            result.append(util.nan)
            samples.append(None)
            number.append(None)
            profiles.append(None)
            continue

        if isinstance(extra_params, list):
            cur_extra_params = extra_params[param_idx]
        else:
            cur_extra_params = extra_params

        res = _run_benchmark_single_param(
            benchmark, benchmark_dir, env, param_idx,
            extra_params=cur_extra_params, profile=profile,
            cwd=cwd)

        result += res.result
        samples += res.samples
        number += res.number

        profiles.append(res.profile)

        if res.stderr:
            stderr += "\n\n"
            stderr += res.stderr

        if res.errcode != 0:
            errcode = res.errcode

    return BenchmarkResult(
        result=result,
        samples=samples,
        number=number,
        errcode=errcode,
        stderr=stderr.strip(),
        profile=_combine_profile_data(profiles)
    )


def _run_benchmark_single_param(benchmark, benchmark_dir, env, param_idx,
                                profile, extra_params, cwd):
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
    result : BenchmarkResult
        Result data.

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

        if errcode != 0:
            if errcode == util.TIMEOUT_RETCODE:
                out += "\n\nasv: benchmark timed out (timeout {0}s)\n".format(benchmark['timeout'])

            result = None
            samples = None
            number = None
        else:
            with open(result_file.name, 'r') as stream:
                data = stream.read()

            try:
                data = json.loads(data)
            except ValueError as exc:
                data = None
                errcode = JSON_ERROR_RETCODE
                out += "\n\nasv: failed to parse benchmark result: {0}\n".format(exc)

            # Special parsing for timing benchmark results
            if isinstance(data, dict) and 'samples' in data and 'number' in data:
                result = True
                samples = data['samples']
                number = data['number']
            else:
                result = data
                samples = None
                number = None

        if benchmark['params'] and out:
            params, = itertools.islice(itertools.product(*benchmark['params']),
                                       param_idx, param_idx + 1)
            out = "For parameters: {0}\n{1}".format(", ".join(params), out)

        if profile:
            with io.open(profile_path, 'rb') as profile_fd:
                profile_data = profile_fd.read()
            profile_data = profile_data if profile_data else None
        else:
            profile_data = None

        return BenchmarkResult(
            result=[result],
            samples=[samples],
            number=[number],
            errcode=errcode,
            stderr=out.strip(),
            profile=profile_data)

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
