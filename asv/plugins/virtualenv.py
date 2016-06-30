# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

from distutils.version import LooseVersion
import sys
import re
import inspect
import os
import subprocess

import six

from .. import environment
from ..console import log
from .. import util


WIN = (os.name == "nt")


class Virtualenv(environment.Environment):
    """
    Manage an environment using virtualenv.
    """
    tool_name = "virtualenv"

    def __init__(self, conf, python, requirements):
        """
        Parameters
        ----------
        conf : Config instance

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        executable : str
            Path to Python executable.

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        executable = Virtualenv._find_python(python)
        if executable is None:
            raise environment.EnvironmentUnavailable(
                "No executable found for python {0}".format(python))

        self._executable = executable
        self._python = python
        self._requirements = requirements
        super(Virtualenv, self).__init__(conf, python, requirements)

        try:
            import virtualenv
        except ImportError:
            raise environment.EnvironmentUnavailable(
                "virtualenv package not installed")

        # Can't use `virtualenv.__file__` here, because that will refer to a
        # .pyc file which can't be used on another version of Python
        self._virtualenv_path = os.path.abspath(
            inspect.getsourcefile(virtualenv))

    @staticmethod
    def _find_python(python):
        """Find Python executable for the given Python version"""
        is_pypy = python.startswith("pypy")

        # Parse python specifier
        if is_pypy:
            executable = python
            if python == 'pypy':
                python_version = '2'
            else:
                python_version = python[4:]
        else:
            python_version = python
            executable = "python{0}".format(python_version)

        # Find Python executable on path
        try:
            return util.which(executable)
        except IOError:
            pass

        # Maybe the current one is correct?
        current_is_pypy = hasattr(sys, 'pypy_version_info')
        current_versions = ['{0[0]}'.format(sys.version_info),
                            '{0[0]}.{0[1]}'.format(sys.version_info)]

        if is_pypy == current_is_pypy and python_version in current_versions:
            return sys.executable

        return None

    @property
    def name(self):
        """
        Get a name to uniquely identify this environment.
        """
        python = self._python
        if self._python.startswith('pypy'):
            # get_env_name adds py-prefix
            python = python[2:]
        return environment.get_env_name(self.tool_name, python, self._requirements)

    @classmethod
    def matches(self, python):
        if not (re.match(r'^[0-9].*$', python) or re.match(r'^pypy[0-9.]*$', python)):
            # The python name should be a version number, or pypy+number
            return False

        try:
            import virtualenv
        except ImportError:
            return False
        else:
            if LooseVersion(virtualenv.__version__) == LooseVersion('1.11.0'):
                log.warn(
                    "asv is not compatible with virtualenv 1.11 due to a bug in "
                    "setuptools.")
            if LooseVersion(virtualenv.__version__) < LooseVersion('1.10'):
                log.warn(
                    "If using virtualenv, it much be at least version 1.10")

        executable = Virtualenv._find_python(python)
        return executable is not None

    def _setup(self):
        """
        Setup the environment on disk using virtualenv.
        Then, all of the requirements are installed into
        it using `pip install`.
        """
        log.info("Creating virtualenv for {0}".format(self.name))
        util.check_call([
            sys.executable,
            self._virtualenv_path,
            '--no-site-packages',
            "-p",
            self._executable,
            self._path])

        log.info("Installing requirements for {0}".format(self.name))
        self._install_requirements()

    def _install_requirements(self):
        if sys.version_info[:2] == (3, 2):
            pip_args = ['install', '-v', 'wheel<0.29.0', 'pip<8']
        else:
            pip_args = ['install', '-v', 'wheel', 'pip>=8']

        if not WIN:
            self.run_executable('pip', pip_args)
        else:
            # Run pip self-upgrade via python -m pip, so that it works on Windows
            self.run_executable('python', ['-m', 'pip'] + pip_args)

        if self._requirements:
            args = ['install', '-v', '--upgrade']
            for key, val in six.iteritems(self._requirements):
                pkg = key
                if key.startswith('pip+'):
                    pkg = key[4:]

                if val:
                    args.append("{0}=={1}".format(pkg, val))
                else:
                    args.append(pkg)
            self.run_executable('pip', args, timeout=self._install_timeout)

    def install(self, package):
        log.info("Installing into {0}".format(self.name))
        self.run_executable('pip', ['install', package],
                            timeout=self._install_timeout)

    def uninstall(self, package):
        log.info("Uninstalling from {0}".format(self.name))
        self.run_executable('pip', ['uninstall', '-y', package],
                            valid_return_codes=None)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self.run_executable('python', args, **kwargs)
