# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import re
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


def run_benchmark(benchmark, root, env, show_stderr=False,
                  quick=False, profile=False, cwd=None, selected_idx=None):
    """
    Run a benchmark in different process in the given environment.

    Parameters
    ----------
    benchmark : Benchmark object

    root : str
        Path to benchmark directory in which to find the benchmark

    env : Environment object

    show_stderr : bool
        When `True`, write the stderr out to the console.

    quick : bool, optional
        When `True`, run the benchmark function exactly once.

    profile : bool, optional
        When `True`, run the benchmark through the `cProfile` profiler
        and save the results.

    cwd : str, optional
        The path to the current working directory to use when running
        the benchmark process.

    selected_idx : str, optional
        The list of parameters combination to run benchmark on. By default
        run all combinations.

    Returns
    -------
    result : dict
        Returns a dictionary with the following keys:

        - `result`: List of numeric values of the benchmarks (one for each parameter
          combination), either returned directly or obtained from `samples` via 
          statistical analysis.

          Values are `None` if benchmark failed or NaN if it was skipped.

          If benchmark is not parameterized, the list contains a single number.

        - `params`: Same as `benchmark['params']`. Empty list if non-parameterized.

        - `samples`: List of lists of sampled raw data points, if benchmark produces
          those and was successful.

        - `number`: Repeact count associated with each sample.

        - `stats`: List of results of statistical analysis of data.

        - `profile`: If `profile` is `True` and run was at least partially successful, 
          this key will be a byte string containing the cProfile data. Otherwise, None.

        - `stderr`: Output produced.

        - `errcode`: Error return code.
    """
    name = benchmark['name']
    result = {'stderr': '', 'profile': None, 'errcode': 0}
    bench_results = []
    bench_profiles = []

    log.step()
    name_max_width = util.get_terminal_width() - 33
    short_name = truncate_left(name, name_max_width)
    initial_message = 'Running {0}'.format(short_name)
    log.info(initial_message)

    def log_result(msg):
        padding_length = util.get_terminal_width() - len(initial_message) - 14 - 1 - len(msg)
        if WIN:
            padding_length -= 1
        padding = " "*padding_length
        log.add(" {0}{1}".format(padding, msg))

    with log.indent():
        if benchmark['params']:
            param_iter = enumerate(itertools.product(*benchmark['params']))
        else:
            param_iter = [(None, None)]

        bad_output = None
        failure_count = 0
        total_count = 0

        result['started_at'] = datetime.datetime.utcnow()

        for param_idx, params in param_iter:
            if (selected_idx is not None and benchmark['params']
                    and param_idx not in selected_idx):
                # Use NaN to mark the result as skipped
                bench_results.append(dict(samples=None, number=None,
                                          result=float('nan'), stats=None))
                bench_profiles.append(None)
                continue
            success, data, profile_data, err, out, errcode = \
                _run_benchmark_single(
                    benchmark, root, env, param_idx,
                    quick=quick, profile=profile,
                    cwd=cwd)

            total_count += 1
            if success:
                if isinstance(data, dict) and 'samples' in data:
                    value, stats = statistics.compute_stats(data['samples'])
                    result_data = dict(samples=data['samples'],
                                       number=data['number'],
                                       result=value,
                                       stats=stats)
                else:
                    result_data = dict(samples=None,
                                       number=None,
                                       result=data,
                                       stats=None)

                bench_results.append(result_data)
                if profile:
                    bench_profiles.append(profile_data)
            else:
                failure_count += 1
                bench_results.append(dict(samples=None, number=None, result=None, stats=None))
                bench_profiles.append(None)
                if data is not None:
                    bad_output = data

            err = err.strip()
            out = out.strip()

            if errcode:
                if errcode == util.TIMEOUT_RETCODE:
                    if err:
                        err += "\n\n"
                    err += "asv: benchmark timed out (timeout {0}s)\n".format(benchmark['timeout'])
                result['errcode'] = errcode

            if err or out:
                err += out
                if benchmark['params']:
                    head_msg = "\n\nFor parameters: %s\n" % (", ".join(params),)
                else:
                    head_msg = ''

                result['stderr'] += head_msg
                result['stderr'] += err

        # Produce result
        for key in ['samples', 'number', 'result', 'stats']:
            result[key] = [x[key] for x in bench_results]

        if benchmark['params']:
            result['params'] = benchmark['params']
            if profile:
                # Produce only a single profile
                profile_data = _combine_profile_data(bench_profiles)
                if profile_data is not None:
                    result['profile'] = profile_data
        else:
            result['params'] = []
            if profile and bench_profiles[0] is not None:
                result['profile'] = bench_profiles[0]

        result['ended_at'] = datetime.datetime.utcnow()

        # Display status
        if failure_count > 0:
            if bad_output is None:
                if failure_count == total_count:
                    log_result("failed")
                else:
                    log_result("{0}/{1} failed".format(failure_count, total_count))
            else:
                log_result("invalid output")
                with log.indent():
                    log.debug(data)

        # Display results
        if benchmark['params'] and show_stderr:
            # Long format display
            if failure_count == 0:
                log_result("ok")

            display_result = [(v, statistics.get_err(v, s) if s is not None else None)
                              for v, s in zip(result['result'], result['stats'])]
            display = _format_benchmark_result(display_result, benchmark)
            log.info("\n" + "\n".join(display))
        else:
            if failure_count == 0:
                # Failure already shown above
                if not bench_results:
                    display = "[]"
                else:
                    if result['stats'][0]:
                        err = statistics.get_err(result['result'][0], result['stats'][0])
                    else:
                        err = None
                    display = util.human_value(result['result'][0], benchmark['unit'], err=err)
                    if len(bench_results) > 1:
                        display += ";..."
                log_result(display)

        # Dump program output
        if show_stderr and result.get('stderr'):
            with log.indent():
                log.error(result['stderr'])

        return result


def _run_benchmark_single(benchmark, root, env, param_idx, profile, quick, cwd):
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
        success = True

        result_file.close()
        out, err, errcode = env.run(
            [BENCHMARK_RUN_SCRIPT, 'run', os.path.abspath(root),
             name, str(quick), profile_path, result_file.name],
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


class Benchmarks(dict):
    """
    Manages and runs the set of benchmarks in the project.
    """
    api_version = 1

    def __init__(self, conf, benchmarks, regex=None):
        """
        Initialize a list of benchmarks.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        benchmarks : list
            Benchmarks as from Benchmarks._disc_benchmarks
            or loaded from a file.

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.
            For parameterized benchmarks, the regex match against
            `funcname(param0, param1, ...)` to include the parameter
            combination in regex filtering.
        """
        self._conf = conf
        self._benchmark_dir = conf.benchmark_dir

        if not regex:
            regex = []
        if isinstance(regex, six.string_types):
            regex = [regex]

        self._all_benchmarks = {}
        self._benchmark_selection = {}
        for benchmark in benchmarks:
            self._all_benchmarks[benchmark['name']] = benchmark
            if benchmark['params']:
                self._benchmark_selection[benchmark['name']] = []
                for idx, param_set in enumerate(
                        itertools.product(*benchmark['params'])):
                    name = '%s(%s)' % (
                        benchmark['name'],
                        ', '.join(param_set))
                    if not regex or any(re.search(reg, name) for reg in regex):
                        self[benchmark['name']] = benchmark
                        self._benchmark_selection[benchmark['name']].append(idx)
            else:
                self._benchmark_selection[benchmark['name']] = None
                if not regex or any(re.search(reg, benchmark['name']) for reg in regex):
                    self[benchmark['name']] = benchmark

    @classmethod
    def discover(cls, conf, repo, environments, commit_hash, regex=None):
        """
        Discover benchmarks in the given `benchmark_dir`.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        repo : Repo object
            The project's repository

        environments : list of Environment
            List of environments available for benchmark discovery.

        commit_hash : list of str
            Commit hashes to use for benchmark discovery.

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.

        """
        benchmarks = cls._disc_benchmarks(conf, repo, environments, commit_hash)
        return cls(conf, benchmarks, regex=regex)

    @classmethod
    def _disc_benchmarks(cls, conf, repo, environments, commit_hashes):
        """
        Discover all benchmarks in a directory tree.
        """
        root = conf.benchmark_dir

        cls.check_tree(root)

        if len(environments) == 0:
            raise util.UserError("No available environments")

        # Append default commit hashes, to make it probably the
        # discovery usually succeeds
        commit_hashes = list(commit_hashes)
        for branch in conf.branches:
            branch_hash = repo.get_hash_from_name(branch)
            if branch_hash not in commit_hashes:
                commit_hashes.append(branch_hash)

        log.info("Discovering benchmarks")
        with log.indent():
            last_err = None
            for env, commit_hash in itertools.product(environments, commit_hashes):
                env.create()

                if last_err is not None:
                    log.warn("Build failed: trying different commit")

                try:
                    env.install_project(conf, repo, commit_hash)
                    break
                except util.ProcessError as err:
                    # Installation failed
                    last_err = err
            else:
                log.error(str(last_err))
                raise util.UserError("Failed to build the project.")

            result_dir = tempfile.mkdtemp()
            try:
                result_file = os.path.join(result_dir, 'result.json')
                env.run(
                    [BENCHMARK_RUN_SCRIPT, 'discover',
                     os.path.abspath(root),
                     os.path.abspath(result_file)],
                    cwd=result_dir,
                    dots=False)

                with open(result_file, 'r') as fp:
                    benchmarks = json.load(fp)
            finally:
                util.long_path_rmtree(result_dir)

        return benchmarks

    @classmethod
    def check_tree(cls, root):
        """
        Check the benchmark tree for files with the same name as
        directories.

        Also, ensure that every directory has an __init__.py file.

        Raises
        ------
        ValueError :
            A .py file and directory with the same name (excluding the
            extension) were found.
        """
        if os.path.basename(root) == '__pycache__':
            return

        if not os.path.isfile(os.path.join(root, '__init__.py')):
            raise util.UserError(
                "No __init__.py file in '{0}'".format(root))

        # First, check for the case where a .py file and a directory
        # have the same name (without the extension).  This can't be
        # handled, so just raise an exception
        found = set()
        for filename in os.listdir(root):
            path = os.path.join(root, filename)
            if os.path.isfile(path):
                filename, ext = os.path.splitext(filename)
                if ext == '.py':
                    found.add(filename)

        for dirname in os.listdir(root):
            path = os.path.join(root, dirname)
            if os.path.isdir(path):
                if dirname in found:
                    raise util.UserError(
                        "Found a directory and python file with same name in "
                        "benchmark tree: '{0}'".format(path))
                cls.check_tree(path)

    @classmethod
    def get_benchmark_file_path(cls, results_dir):
        """
        Get the path to the benchmarks.json file in the results dir.
        """
        return os.path.join(results_dir, "benchmarks.json")

    def save(self):
        """
        Save the ``benchmarks.json`` file, which is a cached set of the
        metadata about the discovered benchmarks, in the results dir.
        """
        path = self.get_benchmark_file_path(self._conf.results_dir)
        util.write_json(path, self._all_benchmarks, self.api_version)

    @classmethod
    def load(cls, conf):
        """
        Load the benchmark descriptions from the `benchmarks.json` file.
        If the file is not found, one of the given `environments` will
        be used to discover benchmarks.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        Returns
        -------
        benchmarks : Benchmarks object
        """
        try:
            path = cls.get_benchmark_file_path(conf.results_dir)
            if not os.path.isfile(path):
                raise util.UserError("Benchmark list file {} missing!".format(path))
            d = util.load_json(path, cleanup=False, api_version=cls.api_version)
            benchmarks = six.itervalues(d)
            return cls(conf, benchmarks)
        except util.UserError as err:
            raise util.UserError("{}\nUse `asv run --bench just-discover` to "
                                 "regenerate benchmarks.json".format(str(err)))

    def run_benchmarks(self, env, show_stderr=False, quick=False, profile=False,
                       skip=None):
        """
        Run all of the benchmarks in the given `Environment`.

        Parameters
        ----------
        env : Environment object
            Environment in which to run the benchmarks.

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

        skip : set, optional
            Benchmark names to skip.

        Returns
        -------
        dict : result
            Returns a dictionary where the keys are benchmark names
            and the values are dictionaries containing information
            about running that benchmark.

            Each of the values in the dictionary has the following
            keys:

            - `result`: The numeric value of the benchmark (usually
              the runtime in seconds for a timing benchmark), but may
              be an arbitrary JSON data structure. For parameterized tests,
              this is a dictionary with keys 'params' and 'result', where
              the value of 'params' contains a list of lists of parameter values,
              and 'result' is a list of results, corresponding to itertools.product
              iteration over parameters.
              Set to `None` if the benchmark failed.

            - `profile`: If `profile` is `True`, this key will exist,
              and be a byte string containing the cProfile data.
        """
        log.info("Benchmarking {0}".format(env.name))

        with log.indent():
            benchmarks = sorted(list(six.iteritems(self)))

            # Remove skipped benchmarks
            if skip:
                benchmarks = [
                    (name, benchmark) for (name, benchmark) in
                    benchmarks if name not in skip]

            # Organize benchmarks by the setup_cache_key
            benchmark_order = {}
            benchmark_timeout = {}
            for name, benchmark in benchmarks:
                key = benchmark.get('setup_cache_key')
                benchmark_order.setdefault(key, []).append((name, benchmark))

                # setup_cache timeout
                benchmark_timeout[key] = max(benchmark.get('setup_cache_timeout',
                                                           benchmark['timeout']),
                                             benchmark_timeout.get(key, 0))

            times = {}
            for setup_cache_key, benchmark_set in six.iteritems(benchmark_order):
                tmpdir = tempfile.mkdtemp()
                try:
                    if setup_cache_key is not None:
                        timeout = benchmark_timeout[setup_cache_key]
                        log.info("Setting up {0}".format(setup_cache_key))
                        out, err, errcode = env.run(
                            [BENCHMARK_RUN_SCRIPT, 'setup_cache',
                             os.path.abspath(self._benchmark_dir),
                             benchmark_set[0][0]],
                            dots=False, display_error=False,
                            return_stderr=True, valid_return_codes=None,
                            cwd=tmpdir, timeout=timeout)
                        if errcode:
                            # Dump program output
                            if show_stderr and err:
                                with log.indent():
                                    log.error(err)

                            for name, benchmark in benchmark_set:
                                # TODO: Store more information about failure
                                timestamp = datetime.datetime.utcnow()
                                times[name] = {'result': None,
                                               'samples': None,
                                               'stats': None,
                                               'params': [],
                                               'stderr': err,
                                               'started_at': timestamp,
                                               'ended_at': timestamp}
                            continue

                    for name, benchmark in benchmark_set:
                        times[name] = run_benchmark(
                            benchmark, self._benchmark_dir, env,
                            show_stderr=show_stderr,
                            quick=quick, profile=profile,
                            cwd=tmpdir,
                            selected_idx=self._benchmark_selection[benchmark['name']])
                finally:
                    shutil.rmtree(tmpdir, True)

        return times

    def skip_benchmarks(self, env):
        """
        Mark benchmarks as skipped.
        """
        log.warn("Skipping {0}".format(env.name))
        with log.indent():
            times = {}
            for name in self:
                log.step()
                log.warn('Benchmark {0} skipped'.format(name))
                timestamp = datetime.datetime.utcnow()
                times[name] = {'result': None,
                               'samples': None,
                               'stats': None,
                               'params': [],
                               'started_at': timestamp,
                               'ended_at': timestamp}
        return times


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
