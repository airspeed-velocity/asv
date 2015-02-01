# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import re
import sys
import tempfile
import itertools

import six

from .console import log, truncate_left
from .environment import get_environments
from .repo import get_repo
from . import util


# Can't use benchmark.__file__, because that points to the compiled
# file, so it can't be run by another version of Python.
BENCHMARK_RUN_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "benchmark.py")


def run_benchmark(benchmark, root, env, show_stderr=False, quick=False,
                  profile=False):
    """
    Run a single benchmark in another process in the given environment.

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

    Returns
    -------
    result : dict
        Returns a dictionary with the following keys:

        - `result`: The numeric value of the benchmark (usually the
          runtime in seconds for a timing benchmark), but may be an
          arbitrary JSON data structure.  Set to `None` if the
          benchmark failed.

        - `profile`: If `profile` is `True`, this key will exist, and
          be a byte string containing the cProfile data.
    """
    name = benchmark['name']
    result = {'result': None}

    log.step()
    name_max_width = util.get_terminal_width() - 33
    short_name = truncate_left(name, name_max_width)
    log.info('Running {0:{1}s}'.format(short_name, name_max_width))

    with log.indent():
        if profile:
            profile_fd, profile_path = tempfile.mkstemp()
            os.close(profile_fd)
        else:
            profile_path = 'None'

        err = ''
        errcode = 0

        result_file = tempfile.NamedTemporaryFile(delete=False)
        try:
            result_file.close()
            out, err, errcode = env.run(
                [BENCHMARK_RUN_SCRIPT, 'run', root, name, str(quick),
                 profile_path, result_file.name],
                dots=False, timeout=benchmark['timeout'],
                display_error=False, return_stderr=True,
                valid_return_codes=None)
            if errcode:
                log.add(" failed".format(name))
            else:
                with open(result_file.name, 'r') as stream:
                    data = stream.read()
                try:
                    parsed = json.loads(data)
                except:
                    log.add(" invalid output".format(name))
                    with log.indent():
                        log.debug(data)
                else:
                    result['result'] = parsed

                    # Display results
                    if not benchmark['params']:
                        display = util.human_value(parsed, benchmark['unit'])
                        log.add(' {0:>8}'.format(display))
                    else:
                        if not parsed['result']:
                            display = util.human_value(parsed['result'], benchmark['unit'])
                            log.add(' {0:>8}'.format(display))
                        elif not show_stderr:
                            display = util.human_value(parsed['result'][0], benchmark['unit']) + ";..."
                            log.add(' {0:>8}'.format(display))
                        else:
                            display = _format_benchmark_result(parsed, benchmark)
                            log.info("\n" + "\n".join(display))

                    if profile:
                        with io.open(profile_path, 'rb') as profile_fd:
                            result['profile'] = profile_fd.read()

            err = err.strip()
            out = out.strip()
            if err or out:
                if show_stderr:
                    with log.indent():
                        log.error(err)
                        log.error(out)

                result['stderr'] = err
                result['stdout'] = out

            if errcode:
                result['errcode'] = errcode

            return result
        finally:
            os.remove(result_file.name)
            if profile:
                os.remove(profile_path)


class Benchmarks(dict):
    """
    Manages and runs the set of benchmarks in the project.
    """
    api_version = 1

    def __init__(self, conf, benchmarks=None, regex=None):
        """
        Discover benchmarks in the given `benchmark_dir`.

        Parameters
        ----------
        conf : Config object
            The project's configuration

        regex : str or list of str, optional
            `regex` is a list of regular expressions matching the
            benchmarks to run.  If none are provided, all benchmarks
            are run.
        """
        self._conf = conf
        self._benchmark_dir = conf.benchmark_dir

        if benchmarks is None:
            benchmarks = self.disc_benchmarks(conf)
        else:
            benchmarks = six.itervalues(benchmarks)

        if not regex:
            regex = []
        if isinstance(regex, six.string_types):
            regex = [regex]

        self._all_benchmarks = {}
        for benchmark in benchmarks:
            self._all_benchmarks[benchmark['name']] = benchmark
            for reg in regex:
                if not re.search(reg, benchmark['name']):
                    break
            else:
                self[benchmark['name']] = benchmark

    @classmethod
    def disc_benchmarks(cls, conf):
        """
        Discover all benchmarks in a directory tree.
        """
        root = conf.benchmark_dir

        cls.check_tree(root)

        environments = list(get_environments(conf))
        if len(environments) == 0:
            raise util.UserError("No available environments")

        # Ideally, use an environment in the same Python version as
        # master, but if one isn't found, just default to the first
        # one.
        this_version = "{0:d}.{1:d}".format(
            sys.version_info[0], sys.version_info[1])
        for env in environments:
            if env.python == this_version:
                break
        else:
            env = environments[0]

        log.info("Discovering benchmarks")
        with log.indent():
            repo = get_repo(conf)
            repo.checkout()

            env.install_project(conf)

            result_file = tempfile.NamedTemporaryFile(delete=False)
            try:
                result_file.close()
                output = env.run(
                    [BENCHMARK_RUN_SCRIPT, 'discover', root,
                     result_file.name],
                    dots=False)

                with open(result_file.name, 'r') as fp:
                    benchmarks = json.load(fp)
            finally:
                os.remove(result_file.name)

            for benchmark in benchmarks:
                yield benchmark

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
        del self._all_benchmarks['version']

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
        def regenerate():
            self = cls(conf)
            self.save()
            return self

        path = cls.get_benchmark_file_path(conf.results_dir)
        if not os.path.isfile(path):
            return regenerate()

        d = util.load_json(path, cleanup=False)
        version = d['version']
        del d['version']
        if version != cls.api_version:
            # Just re-do the discovery if the file is the wrong
            # version
            return regenerate()

        return cls(conf, benchmarks=d)

    def run_benchmarks(self, env, show_stderr=False, quick=False, profile=False):
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
            times = {}
            benchmarks = sorted(list(six.iteritems(self)))
            for name, benchmark in benchmarks:
                times[name] = run_benchmark(
                    benchmark, self._benchmark_dir, env, show_stderr=show_stderr,
                    quick=quick, profile=profile)
        return times

    def skip_benchmarks(self, env):
        """
        Mark all of the benchmarks as skipped.
        """
        log.warn("Skipping {0}".format(env.name))
        with log.indent():
            times = {}
            for name in self:
                log.step()
                log.warn('Benchmark {0} skipped'.format(name))
                times[name] = {'result': None}
        return times


def _format_benchmark_result(result, benchmark, max_width=None):
    """
    Format the result from a parameterized benchmark as an ASCII table
    """
    if not result['result']:
        return ['[]']

    # Fold result to a table
    if max_width is None:
        max_width = util.get_terminal_width() * 3//4

    # Determine which (if any) parameters can be fit to columns
    column_params = []
    width = 1
    for j in range(len(benchmark['params'])-1, 0, -1):
        width *= max(16 * len(benchmark['params'][j]),
                     len(benchmark['param_names'][j]) + 2)
        if width > max_width:
            break
        column_params.append(benchmark['params'][j])

    # Generate output
    rows = []
    if column_params:
        row_params = benchmark['params'][:-len(column_params)]
        header = benchmark['param_names'][:len(row_params)]
        column_param_permutations = list(itertools.product(*column_params))
        header += ["/".join(map(str, x)) for x in column_param_permutations]
        rows.append(header)
        column_items = len(column_param_permutations)
        name_header = "/".join(benchmark['param_names'][len(row_params):])
    else:
        column_items = 1
        row_params = benchmark['params']
        name_header = ""
        header = benchmark['param_names']
        rows.append(header)

    result = result['result']

    for j, values in enumerate(itertools.product(*row_params)):
        row_results = [util.human_value(x, benchmark['unit'])
                       for x in result[j*column_items:(j+1)*column_items]]
        row = list(values) + row_results
        rows.append(row)

    if name_header:
        display = util.format_text_table(rows, 1, 
                                         top_header_text=name_header,
                                         top_header_span_start=len(row_params))
    else:
        display = util.format_text_table(rows, 1)
    return display.splitlines()
