# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import base64
import os
import zlib

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
    for (root, filename) in iter_results_paths(
            os.path.join(results, machine_name)):
        results_commit = filename.split('-')[0]
        max_len = max(len(commit), len(results_commit))
        if results_commit[:max_len] == commit[:max_len]:
            yield Results.load(os.path.join(root, filename))


def iter_existing_hashes(results):
    """
    Iterate over all of the result commit hashes and dates.  Each
    element yielded is the pair (hash, date).

    May return duplicates.  Use `get_existing_hashes` if that matters.
    """
    for result in iter_results(results):
        yield result.commit_hash, result.date


def get_existing_hashes(results):
    """
    Get all of the commit hashes that have already been tested.

    Each element yielded is the pair (hash, date).
    """
    log.info("Getting existing hashes")
    hashes = list(set(iter_existing_hashes(results)))
    return hashes


def find_latest_result_hash(machine, root):
    """
    Find the latest result for the given machine.
    """
    root = os.path.join(root, machine)

    latest_date = 0
    latest_hash = ''
    for commit_hash, date in iter_existing_hashes(root):
        if date > latest_date:
            latest_date = date
            latest_hash = commit_hash

    return latest_hash


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


class Results(object):
    """
    Manage a set of benchmark results for a single machine and commit
    hash.
    """
    api_version = 1

    def __init__(self, params, requirements, commit_hash, date, python):
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
        """
        self._params = params
        self._requirements = requirements
        self._commit_hash = commit_hash
        self._date = date
        self._results = {}
        self._profiles = {}
        self._python = python

        self._filename = get_filename(
            params['machine'], self._commit_hash,
            environment.get_env_name(python, requirements))

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
        Save the results to disk.

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
            'python': self._python,
            'profiles': self._profiles
        }, self.api_version)

    @classmethod
    def load(cls, path):
        """
        Load results from disk.

        Parameters
        ----------
        path : str
            Path to results file.
        """
        d = util.load_json(path, cls.api_version)

        obj = cls(
            d['params'],
            d['requirements'],
            d['commit_hash'],
            d['date'],
            d['python']
        )
        obj._results = d['results']
        if 'profiles' in d:
            obj._profiles = d['profiles']
        obj._filename = os.path.join(*path.split(os.path.sep)[-2:])
        return obj

    def rm(self, result_dir):
        path = os.path.join(result_dir, self._filename)
        os.remove(path)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
