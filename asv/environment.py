# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Manages an environment -- a combination of a version of Python and set
of dependencies.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil

import six

from .console import console
from . import util


def get_environments(env_dir, pythons, matrix):
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
        entry = matrix.pop(key)

        for result in iter_matrix(matrix):
            result = dict(result)
            if len(entry):
                for value in entry:
                    result[key] = value
                    yield result
            else:
                result[key] = None
                yield result

    for python in pythons:
        for configuration in iter_matrix(matrix):
            yield Environment(env_dir, python, configuration)


class Environment(object):
    """
    Manage a single environment -- a combination of a particular
    version of Python and a set of dependencies for the benchmarked
    project.

    Environments are created in the
    """
    def __init__(self, env_dir, python, requirements):
        """
        Parameters
        ----------
        env_dir : str
            Root path in which to cache environments on disk.

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        executables = util.which("python{0}".format(python))
        if len(executables) == 0:
            raise RuntimeError(
                "No executable found for version {0}".format(python))
        self._executable = executables
        self._env_dir = env_dir
        self._python = python
        self._requirements = requirements
        self._path = os.path.join(
            self._env_dir, self.name)

        self._virtualenv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'extern', 'virtualenv.py')

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
        created using virtualenv.  Then, all of the requirements are
        installed into it using `pip install`.
        """
        if not os.path.exists(self._env_dir):
            os.mkdir(self._env_dir)

        try:
            if not os.path.exists(self._path):
                util.check_call([
                    self._executable,
                    self._virtualenv_path,
                    '--no-site-packages',
                    self._path])
        except:
            if os.path.exists(self._path):
                shutil.rmtree(self._path)
            raise

        self.upgrade('setuptools')

        for key, val in six.iteritems(self._requirements):
            if val is not None:
                self.install("{0}=={1}".format(key, val))
            else:
                self.install(key)

    def _run_executable(self, executable, args, **kwargs):
        return util.check_output([
            os.path.join(self._path, 'bin', executable)] + args, **kwargs)

    def install(self, package):
        """
        Install a package into the environment using `pip install`.
        """
        console.message("Installing {0}".format(package))
        self._run_executable('pip', ['install', package])

    def upgrade(self, package):
        """
        Upgrade a package into the environment using `pip install --upgrade`.
        """
        console.message("Installing {0}".format(package))
        self._run_executable('pip', ['install', '--upgrade', package])

    def uninstall(self, package):
        """
        Uninstall a package into the environment using `pip uninstall`.
        """
        console.message("Uninstalling {0}".format(package))
        self._run_executable('pip', ['uninstall', '-y', package], error=False)

    def run(self, args, **kwargs):
        """
        Start up the environment's python executable with the given
        args.
        """
        return self._run_executable('python', args, **kwargs)
