# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import inspect
import os
import shutil

import six

from .. import environment
from ..console import log
from .. import util


class Virtualenv(environment.Environment):
    """
    Manage an environment using virtualenv.
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
        self._executable = executable
        self._env_dir = env_dir
        self._python = python
        self._requirements = requirements
        self._path = os.path.join(
            self._env_dir, self.name)

        try:
            import virtualenv
        except ImportError:
            raise RuntimeError(
                "virtualenv must be installed to run asv with the given "
                "Python executable")

        # Can't use `virtualenv.__file__` here, because that will refer to a
        # .pyc file which can't be used on another version of Python
        self._virtualenv_path = os.path.abspath(
            inspect.getsourcefile(virtualenv))

        self._is_setup = False
        self._requirements_installed = False

    @classmethod
    def get_environments(cls, conf, python):
        try:
            executable = util.which('python{0}'.format(python))
        except IOError:
            log.warn("No executable found for python {0}".format(python))
        else:
            for configuration in environment.iter_configuration_matrix(conf.matrix):
                yield cls(conf.env_dir, python, executable, configuration)

    @classmethod
    def matches(self, python):
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
        if self._is_setup:
            return

        if not os.path.exists(self._env_dir):
            os.makedirs(self._env_dir)

        try:
            log.info("Creating virtualenv for {0}".format(self.name))
            if not os.path.exists(self._path):
                util.check_call([
                    self._executable,
                    self._virtualenv_path,
                    '--no-site-packages',
                    self._path])
        except:
            log.error("Failure creating virtualenv for {0}".format(self.name))
            if os.path.exists(self._path):
                shutil.rmtree(self._path)
            raise

        self._is_setup = True

    def install_requirements(self):
        if self._requirements_installed:
            return

        self.setup()

        self.upgrade('setuptools==3.8')

        for key, val in six.iteritems(self._requirements):
            if val is not None:
                self.upgrade("{0}=={1}".format(key, val))
            else:
                self.upgrade(key)

        self._requirements_installed = True

    def _run_executable(self, executable, args, **kwargs):
        return util.check_output([
            os.path.join(self._path, 'bin', executable)] + args, **kwargs)

    def install(self, package, editable=False):
        rel = os.path.relpath(package, os.getcwd())
        log.info("Installing {0} into {1}".format(rel, self.name))
        args = ['install']
        if editable:
            args.append('-e')
        args.append(package)
        self._run_executable('pip', args)

    def upgrade(self, package):
        log.info("Upgrading {0} in {1}".format(package, self.name))
        self._run_executable('pip', ['install', '--upgrade', package])

    def uninstall(self, package):
        log.info("Uninstalling {0} from {1}".format(package, self.name))
        self._run_executable('pip', ['uninstall', '-y', package], error=False)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        self.install_requirements()
        return self._run_executable('python', args, **kwargs)
