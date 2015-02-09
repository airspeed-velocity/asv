# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

from distutils.version import LooseVersion
import inspect
import os

import six

from .. import environment
from ..console import log
from .. import util


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

    @classmethod
    def get_environments(cls, conf, python):
        try:
            executable = util.which('python{0}'.format(python))
        except IOError:
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

        try:
            util.which('python{0}'.format(python))
        except IOError:
            return False
        else:
            return True

    def setup(self):
        """
        Setup the environment on disk.  If it doesn't exist, it is
        created using virtualenv.  Then, all of the requirements are
        installed into it using `pip install`.
        """
        log.info("Creating virtualenv for {0}".format(self.name))
        util.check_call([
            self._executable,
            self._virtualenv_path,
            '--no-site-packages',
            self._path])

    def install_requirements(self):
        if self._requirements_installed:
            return

        self.create()

        self._run_executable('pip', ['install', '--upgrade',
                                     'setuptools'])
        self._run_executable('pip', ['install', 'wheel'])

        if self._requirements:
            args = ['install', '--upgrade']
            for key, val in six.iteritems(self._requirements):
                if val is not None:
                    args.append("{0}=={1}".format(key, val))
                else:
                    args.append(key)
            self._run_executable('pip', args)

        self._requirements_installed = True

    def _run_executable(self, executable, args, **kwargs):
        return util.check_output([
            os.path.join(self._path, 'bin', executable)] + args, **kwargs)

    def install(self, package):
        log.info("Installing into {0}".format(self.name))
        self._run_executable('pip', ['install', package])

    def uninstall(self, package):
        log.info("Uninstalling from {0}".format(self.name))
        self._run_executable('pip', ['uninstall', '-y', package],
                             valid_return_codes=None)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        self.install_requirements()
        return self._run_executable('python', args, **kwargs)
