# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from .environment import Environment
from . import util


def iter_results(results):
    """
    Iterate over all of the result files.
    """
    skip_files = set([
        'machine.json', 'benchmarks.json'
    ])
    for root, dirs, files in os.walk(results):
        for filename in files:
            if filename not in skip_files and filename.endswith('.json'):
                path = os.path.join(root, filename)
                try:
                    result = Results.load(path)
                except:
                    continue
                yield result


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


class Results(object):
    """
    Manage a set of benchmark results for a single machine and commit
    hash.
    """
    api_version = 1

    def __init__(self, params, env, commit_hash, date):
        """
        Parameters
        ----------
        params : dict
            Parameters describing the environment in which the
            benchmarks were run.

        env : Environment object
            Environment in which the benchmarks were run.

        commit_hash : str
            The commit hash for the benchmark run.

        date : int
            Javascript timestamp for when the commit was merged into
            the repository.
        """
        self._params = params
        self._env = env
        self._commit_hash = commit_hash
        self._date = date
        self._results = {}
        self._python = env.python

        self._filename = os.path.join(
            params['machine'],
            "{0}-{1}.json".format(
                self._commit_hash[:8],
                env.name))

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
    def env(self):
        return self._env

    def add_times(self, times):
        """
        Add benchmark times.

        Parameters
        ----------
        times : dict
            Dictionary mapping benchmark name to runtime (in seconds).
        """
        self._results.update(times)

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
            'requirements': self._env.requirements,
            'commit_hash': self._commit_hash,
            'date': self._date,
            'python': self._python
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
            Environment('', d['python'], d['requirements']),
            d['commit_hash'],
            d['date'])
        obj.add_times(d['results'])
        obj._filename = os.path.join(*path.split(os.path.sep)[-2:])
        return obj

    def rm(self, result_dir):
        path = os.path.join(result_dir, self._filename)
        os.remove(path)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
