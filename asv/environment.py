# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Manages an environment -- a combination of a version of Python and set
of dependencies.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import os

import six

from .console import log
from .repo import get_repo
from . import util


def get_environments(conf):
    """
    Iterator returning `Environment` objects for all of the
    permutations of the given versions of Python and a matrix of
    requirements.

    Parameters
    ----------
    env_dir : str
        Root path in which to cache environments on disk.

    pythons : sequence of str
        A list of versions of Python

    matrix : dict of package to sequence of versions
    """
    def iter_matrix(matrix):
        if len(matrix) == 0:
            yield dict()
            return

        # TODO: Deal with matrix exclusions
        matrix = dict(matrix)
        key = next(six.iterkeys(matrix))
        entry = matrix[key]
        del matrix[key]

        for result in iter_matrix(matrix):
            if len(entry):
                for value in entry:
                    d = dict(result)
                    d[key] = value
                    yield d
            else:
                d = dict(result)
                d[key] = None
                yield d

    for python in conf.pythons:
        for configuration in iter_matrix(conf.matrix):
            try:
                yield get_environment(conf.env_dir, python, configuration)
            except PythonMissingError:
                log.warn("No executable found for python {0}".format(python))
                break


class PythonMissingError(BaseException):
    pass


class Environment(object):
    """
    Manage a single environment -- a combination of a particular
    version of Python and a set of dependencies for the benchmarked
    project.

    Environments are created in the
    """
    def __init__(self, env_dir, python, executable, requirements):
        """
        Parameters
        ----------
        env_dir : str
            Root path in which to cache environments on disk.

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        executable : str
            Path to Python executable.

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        raise NotImplementedError()

    @classmethod
    def matches(self, executable):
        return False

    @property
    def path(self):
        """
        Return the path to the environment.
        """
        raise NotImplementedError()

    @property
    def name(self):
        """
        Get a name to uniquely identify this environment.
        """
        name = ["py{0}".format(self._python)]
        reqs = list(six.iteritems(self._requirements))
        reqs.sort()
        for key, val in reqs:
            if val is not None:
                name.append(''.join([key, val]))
            else:
                name.append(key)
        return '-'.join(name)

    @property
    def requirements(self):
        return self._requirements

    @property
    def python(self):
        return self._python

    def setup(self):
        """
        Setup the environment on disk.  If it doesn't exist, it is
        created.  Then, all of the requirements are installed into it.
        """
        raise NotImplementedError()

    def install_requirements(self):
        raise NotImplementedError()

    def install(self, package, editable=False):
        """
        Install a package into the environment.
        """
        raise NotImplementedError()

    def upgrade(self, package):
        """
        Upgrade a package into the environment.
        """
        raise NotImplementedError()

    def uninstall(self, package):
        """
        Uninstall a package into the environment.
        """
        raise NotImplementedError()

    def run(self, args, **kwargs):
        """
        Start up the environment's python executable with the given
        args.
        """
        raise NotImplementedError()

    def install_project(self, conf):
        """
        Install a working copy of the benchmarked project into the
        environment.  Uninstalls any installed copy of the project
        first.
        """
        self.install_requirements()

        repo = get_repo(conf)
        commit_hash = repo.get_hash_from_head()

        same_commit = False
        commit_file = os.path.join(self.path, "commit_hash")
        if os.path.exists(commit_file):
            with io.open(commit_file, 'r', encoding='ascii') as fd:
                current_hash = fd.read().strip()
            min_len = min(len(current_hash), len(commit_hash))
            if (min_len > 8 and
                current_hash[:min_len] == commit_hash[:min_len]):
                same_commit = True

        if not same_commit:
            self.uninstall(conf.project)
            self.install(os.path.abspath(conf.project))
            with io.open(commit_file, 'w', encoding='ascii') as fd:
                fd.write(commit_hash)


def get_environment(env_dir, python, requirements):
    """
    Get an Environment subclass for the given Python executable.
    """
    try:
        executable = util.which("python{0}".format(python))
    except RuntimeError:
        raise PythonMissingError()

    # Try the subclasses in reverse order so custom plugins come first
    for cls in list(util.iter_subclasses(Environment))[::-1]:
        if cls.matches(executable):
            return cls(env_dir, python, executable, requirements)

    return Environment.default_class(env_dir, python, executable, requirements)
