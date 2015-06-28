# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

from distutils.version import LooseVersion
import sys
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

    def __init__(self, conf, python, executable, requirements):
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
        self._executable = executable
        self._python = python
        self._requirements = requirements
        super(Virtualenv, self).__init__(conf)

        try:
            import virtualenv
        except ImportError:
            raise util.UserError(
                "virtualenv must be installed to run asv with the given "
                "Python executable")

        # Can't use `virtualenv.__file__` here, because that will refer to a
        # .pyc file which can't be used on another version of Python
        self._virtualenv_path = os.path.abspath(
            inspect.getsourcefile(virtualenv))

    @staticmethod
    def _find_python(python):
        """Find Python executable for the given Python version"""
        # Find Python executable on path
        try:
            return util.which('python{0}'.format(python))
        except IOError:
            pass

        # Maybe the current one is correct
        if '{0[0]}.{0[1]}'.format(sys.version_info) == python:
            return sys.executable

        return None

    @classmethod
    def get_environments(cls, conf, python):
        executable = Virtualenv._find_python(python)
        if executable is None:
            log.warn("No executable found for python {0}".format(python))
        else:
            for configuration in environment.iter_configuration_matrix(conf.matrix):
                yield cls(conf, python, executable, configuration)

    @classmethod
    def matches(self, python):
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

    def setup(self):
        """
        Setup the environment on disk using virtualenv.
        Then, all of the requirements are installed into
        it using `pip install`.
        """
        log.info("Creating virtualenv for {0}".format(self.name))
        util.check_call([
            self._executable,
            self._virtualenv_path,
            '--no-site-packages',
            self._path])

        log.info("Installing requirements for {0}".format(self.name))
        self._install_requirements()

    def _install_requirements(self):
        self.run_executable('pip', ['install', 'wheel'])

        if self._requirements:
            args = ['install', '--upgrade']
            for key, val in six.iteritems(self._requirements):
                if val is not None:
                    args.append("{0}=={1}".format(key, val))
                else:
                    args.append(key)
            self.run_executable('pip', args)

    def install(self, package):
        log.info("Installing into {0}".format(self.name))
        self.run_executable('pip', ['install', package])

    def uninstall(self, package):
        log.info("Uninstalling from {0}".format(self.name))
        self.run_executable('pip', ['uninstall', '-y', package],
                             valid_return_codes=None)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self.run_executable('python', args, **kwargs)
