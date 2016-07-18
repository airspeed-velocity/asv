# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import base64
import os
import zlib
import itertools
import datetime

import six
from six.moves import zip as izip

from . import environment
from .console import log
from .machine import Machine
from . import util


def iter_results_paths(results):
    """
    Iterate over all of the result file paths.
    """
    skip_files = set([
        'machine.json', 'benchmarks.json'
    ])
    for root, dirs, files in os.walk(results):
        # Iterate over files only if machine.json is valid json
        machine_json = os.path.join(root, "machine.json")
        try:
            data = util.load_json(machine_json, api_version=Machine.api_version)
            machine_name = data.get('machine')
            if not isinstance(machine_name, six.text_type):
                raise util.UserError("malformed {0}".format(machine_json))
        except util.UserError as err:
            machine_json_err = "Skipping results: {0}".format(six.text_type(err))
        except IOError as err:
            machine_json_err = "Skipping results: could not load {0}".format(
                machine_json)
        else:
            machine_json_err = None

        # Iterate over files
        for filename in files:
            if filename not in skip_files and filename.endswith('.json'):
                if machine_json_err is not None:
                    # Show the warning only if there are some files to load
                    log.warn(machine_json_err)
                    break

                yield (root, filename, machine_name)


def iter_results(results):
    """
    Iterate over all of the result files.
    """
    for (root, filename, machine_name) in iter_results_paths(results):
        try:
            yield Results.load(os.path.join(root, filename), machine_name=machine_name)
        except util.UserError as exc:
            log.warn(six.text_type(exc))


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

    for (root, filename, machine_name) in iter_results_paths(
            os.path.join(results, machine_name)):
        results_commit = filename.split('-')[0]
        if results_commit == full_commit:
            try:
                yield Results.load(os.path.join(root, filename), machine_name=machine_name)
            except util.UserError as exc:
                log.warn(six.text_type(exc))


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

    path = os.path.join(results, machine_name)

    for (root, filename, r_machine_name) in iter_results_paths(path):
        if r_machine_name != machine_name:
            log.warn("Skipping results '{0}': machine name is not '{1}'".format(
                os.path.join(root, filename), machine_name))
            continue

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
        self._started_at = {}
        self._ended_at = {}

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

    @property
    def started_at(self):
        return self._started_at

    @property
    def ended_at(self):
        return self._ended_at

    def add_result(self, benchmark_name, result, started_at, ended_at):
        """
        Add benchmark result.

        Parameters
        ----------
        benchmark_name : str
            Name of benchmark

        result : {float, dict}
            Result of the benchmark. A number, or for parameterized benchmarks
            a dictionary ``{'result': number, 'params': [param1, ...], ...}``

        started_at : datetime
            Datetime when the benchmark run started

        ended_at : datetime
            Datetime when the benchmark run ended
        """
        self._results[benchmark_name] = result
        self._started_at[benchmark_name] = util.datetime_to_js_timestamp(started_at)
        self._ended_at[benchmark_name] = util.datetime_to_js_timestamp(ended_at)

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

        data = {
            'results': self._results,
            'params': self._params,
            'requirements': self._requirements,
            'commit_hash': self._commit_hash,
            'date': self._date,
            'env_name': self._env_name,
            'python': self._python,
            'profiles': self._profiles,
            'started_at': self._started_at,
            'ended_at': self._ended_at
        }

        util.write_json(path, data, self.api_version)

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
    def load(cls, path, machine_name=None):
        """
        Load results from disk.

        Parameters
        ----------
        path : str
            Path to results file.
        machine_name : str, optional
            If given, check that the results file is for the given machine.

        """
        d = util.load_json(path, cls.api_version, cleanup=False)

        try:
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

            obj._started_at = d.get('started_at', {})
            obj._ended_at = d.get('ended_at', {})
        except KeyError as exc:
            raise util.UserError(
                "Error loading results file '{0}': missing key {1}".format(
                    path, six.text_type(exc)))

        if machine_name is not None and obj.params.get('machine') != machine_name:
            raise util.UserError(
                "Error loading results file '{0}': machine name is not '{1}'".format(
                    path, machine_name))

        return obj

    def add_existing_results(self, old):
        """
        Add any existing old results that aren't overridden by the
        current results.
        """
        for dict_name in ('_results', '_profiles', '_started_at', '_ended_at'):
            old_dict = getattr(old, dict_name)
            new_dict = getattr(self, dict_name)
            for key, val in six.iteritems(old_dict):
                if key not in new_dict:
                    new_dict[key] = val

    def rm(self, result_dir):
        path = os.path.join(result_dir, self._filename)
        os.remove(path)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
