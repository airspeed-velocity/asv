# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import base64
import os
import zlib
import itertools

import six
from six.moves import zip as izip

from . import environment
from .console import log
from . import util


def iter_results_paths(results):
    """
    Iterate over all of the result file paths.
    """
    skip_files = set([
        'machine.json', 'benchmarks.json'
    ])
    for root, dirs, files in os.walk(results):
        for filename in files:
            if filename not in skip_files and filename.endswith('.json'):
                yield (root, filename)


def iter_results(results):
    """
    Iterate over all of the result files.
    """
    for (root, filename) in iter_results_paths(results):
        yield Results.load(os.path.join(root, filename))


def iter_results_for_machine(results, machine_name):
    """
    Iterate over all of the result files for a particular machine.
    """
    return iter_results(os.path.join(results, machine_name))


def iter_results_for_machine_and_hash(results, machine_name, commit):
    """
    Iterate over all of the result files with a given hash for a
    particular machine.
    """
    full_commit = get_result_hash_from_prefix(results, machine_name, commit)

    for (root, filename) in iter_results_paths(
            os.path.join(results, machine_name)):
        results_commit = filename.split('-')[0]
        if results_commit == full_commit:
            yield Results.load(os.path.join(root, filename))


def iter_existing_hashes(results):
    """
    Iterate over all of the result commit hashes and dates and yields
    commit_hash.

    May return duplicates.  Use `get_existing_hashes` if that matters.
    """
    for result in iter_results(results):
        yield result.commit_hash


def get_existing_hashes(results):
    """
    Get a list of the commit hashes that have already been tested.
    """
    log.info("Getting existing hashes")
    hashes = list(set(iter_existing_hashes(results)))
    return hashes


def get_result_hash_from_prefix(results, machine_name, commit_prefix):
    """
    Get the 8-char result commit identifier from a potentially shorter
    prefix. Only considers the set of commits that have had
    results computed.

    Returns None if there are no matches. Raises a UserError
    if the prefix is non-unique.
    """
    commits = set([])

    for (root, filename) in iter_results_paths(os.path.join(results,
                                                            machine_name)):
        results_commit = filename.split('-')[0]
        cmp_len = min(len(commit_prefix), len(results_commit))
        if results_commit[:cmp_len] == commit_prefix[:cmp_len]:
            commits.add(results_commit)

    if len(commits) > 1:
        commit_list_str = ', '.join(sorted(commits))
        raise util.UserError('Git hash prefix could represent one of ' +
                             'multiple commits: {0}'.format(commit_list_str))
    elif len(commits) == 1:
        return list(commits)[0]
    else:
        return None


def get_filename(machine, commit_hash, env_name):
    """
    Get the result filename for a given machine, commit_hash and
    environment.
    """
    return os.path.join(
        machine,
        "{0}-{1}.json".format(
            commit_hash[:8],
            env_name))


def compatible_results(result, benchmark):
    """
    For parameterized benchmarks, obtain values from *result* that
    are compatible with parameters of *benchmark*
    """
    if not benchmark or not benchmark.get('params'):
        # Not a parameterized benchmark, or a benchmark that is not
        # currently there. The javascript side doesn't know how to
        # visualize benchmarks unless the params are the same as those
        # of the current benchmark. Single floating point values are
        # OK, but not parameterized ones.
        if isinstance(result, dict):
            return None
        else:
            return result

    if result is None:
        # All results missing, eg. build failure
        return result

    if not isinstance(result, dict) or 'params' not in result:
        # Not a parameterized result -- test probably was once
        # non-parameterized
        return None

    # Pick results for those parameters that also appear in the
    # current benchmark
    old_results = {}
    for param, value in izip(itertools.product(*result['params']),
                             result['result']):
        old_results[param] = value

    new_results = []
    for param in itertools.product(*benchmark['params']):
        new_results.append(old_results.get(param))
    return new_results


class Results(object):
    """
    Manage a set of benchmark results for a single machine and commit
    hash.
    """
    api_version = 1

    def __init__(self, params, requirements, commit_hash, date, python, env_name):
        """
        Parameters
        ----------
        params : dict
            Parameters describing the environment in which the
            benchmarks were run.

        requirements : list
            Requirements of the benchmarks being run.

        commit_hash : str
            The commit hash for the benchmark run.

        date : int
            Javascript timestamp for when the commit was merged into
            the repository.

        python : str
            A Python version specifier.

        env_name : str
            Environment name
        """
        self._params = params
        self._requirements = requirements
        self._commit_hash = commit_hash
        self._date = date
        self._results = {}
        self._profiles = {}
        self._python = python
        self._env_name = env_name

        self._filename = get_filename(
            params['machine'], self._commit_hash, env_name)

    @property
    def commit_hash(self):
        return self._commit_hash

    @property
    def date(self):
        return self._date

    @property
    def params(self):
        return self._params

    @property
    def results(self):
        return self._results

    def add_time(self, benchmark_name, time):
        """
        Add benchmark times.

        Parameters
        ----------
        benchmark_name : str
            Name of benchmark

        time : number
            Numeric result
        """
        self._results[benchmark_name] = time

    def add_profile(self, benchmark_name, profile):
        """
        Add benchmark profile data.

        Parameters
        ----------
        benchmark_name : str
            Name of benchmark

        profile : bytes
            `cProfile` data
        """
        self._profiles[benchmark_name] = base64.b64encode(
            zlib.compress(profile))

    def get_profile(self, benchmark_name):
        """
        Get the profile data for the given benchmark name.
        """
        return zlib.decompress(
            base64.b64decode(self._profiles[benchmark_name]))

    def has_profile(self, benchmark_name):
        """
        Does the given benchmark data have profiling information?
        """
        return benchmark_name in self._profiles

    def save(self, result_dir):
        """
        Save the results to disk, replacing existing results.

        Parameters
        ----------
        result_dir : str
            Path to root of results tree.
        """
        path = os.path.join(result_dir, self._filename)

        util.write_json(path, {
            'results': self._results,
            'params': self._params,
            'requirements': self._requirements,
            'commit_hash': self._commit_hash,
            'date': self._date,
            'env_name': self._env_name,
            'python': self._python,
            'profiles': self._profiles
        }, self.api_version)

    def update_save(self, result_dir):
        """
        Save the results to disk, adding to any existing results.

        Parameters
        ----------
        result_dir : str
            Path to root of results tree.
        """
        path = os.path.join(result_dir, self._filename)

        if os.path.isfile(path):
            old_results = self.load(path)
            self.add_existing_results(old_results)

        self.save(result_dir)

    @classmethod
    def load(cls, path):
        """
        Load results from disk.

        Parameters
        ----------
        path : str
            Path to results file.
        """
        d = util.load_json(path, cls.api_version, cleanup=False)

        obj = cls(
            d['params'],
            d['requirements'],
            d['commit_hash'],
            d['date'],
            d['python'],
            d.get('env_name',
                  environment.get_env_name('', d['python'], d['requirements']))
        )
        obj._results = d['results']
        if 'profiles' in d:
            obj._profiles = d['profiles']
        obj._filename = os.path.join(*path.split(os.path.sep)[-2:])
        return obj

    def add_existing_results(self, old):
        """
        Add any existing old results that aren't overridden by the
        current results.
        """
        for key, val in six.iteritems(old.results):
            if key not in self._results:
                self._results[key] = val
        for key, val in six.iteritems(old._profiles):
            if key not in self._profiles:
                self._profiles[key] = val

    def rm(self, result_dir):
        path = os.path.join(result_dir, self._filename)
        os.remove(path)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
