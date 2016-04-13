# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import re
import os
import tempfile
import subprocess

import six

from .. import environment
from ..console import log
from .. import util


WIN = (os.name == "nt")


class Conda(environment.Environment):
    """
    Manage an environment using conda.

    Dependencies are installed using ``conda``.  The benchmarked
    project is installed using ``pip`` (since ``conda`` doesn't have a
    method to install from an arbitrary ``setup.py``).
    """
    tool_name = "conda"

    def __init__(self, conf, python, requirements):
        """
        Parameters
        ----------
        conf : Config instance

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        self._python = python
        self._requirements = requirements
        super(Conda, self).__init__(conf, python, requirements)

    @classmethod
    def matches(self, python):
        if not re.match(r'^[0-9].*$', python):
            # The python name should be a version number
            return False

        try:
            conda = util.which('conda')
        except IOError:
            return False
        else:
            # This directory never gets created, since we're just
            # doing a dry run below.  All it needs to be is something
            # that doesn't already exist.
            path = os.path.join(tempfile.gettempdir(), 'check')
            # Check that the version number is valid
            try:
                util.check_call([
                    conda,
                    'create',
                    '--yes',
                    '-p',
                    path,
                    'python={0}'.format(python),
                    '--dry-run'], display_error=False, dots=False)
            except util.ProcessError:
                return False
            else:
                return True

    def _setup(self):
        try:
            conda = util.which('conda')
        except IOError as e:
            raise util.UserError(str(e))

        log.info("Creating conda environment for {0}".format(self.name))
        util.check_call([
            conda,
            'create',
            '--yes',
            '-p',
            self._path,
            '--use-index-cache',
            'python={0}'.format(self._python),
            'pip'])

        log.info("Installing requirements for {0}".format(self.name))
        self._install_requirements(conda)

    def _install_requirements(self, conda):
        self.install('wheel')
        if self._requirements:
            # Install all the dependencies with a single conda command.
            # This ensures we get the versions requested, or an error
            # otherwise. It's also quicker than doing it one by one.
            conda_args = []
            pip_args = []

            for key, val in six.iteritems(self._requirements):
                if key.startswith('pip+'):
                    if val:
                        pip_args.append("{0}=={1}".format(key[4:], val))
                    else:
                        pip_args.append(key[4:])
                else:
                    if val:
                        conda_args.append("{0}={1}".format(key, val))
                    else:
                        conda_args.append(key)

            conda_cmd = ['install', '-p', self._path, '--yes']
            pip_cmd = ['install', '-v', '--upgrade']

            # install conda packages
            if conda_args:
                util.check_output([conda] + conda_cmd + conda_args)
            # install packages only available with pip
            if pip_args:
                self.run_executable('pip', pip_cmd + pip_args,
                                    timeout=self._install_timeout)

    def install(self, package):
        log.info("Installing into {0}".format(self.name))
        self.run_executable('pip', ['install', package])

    def uninstall(self, package):
        log.info("Uninstalling from {0}".format(self.name))
        self.run_executable('pip', ['uninstall', '-y', package],
                            valid_return_codes=None,
                            timeout=self._install_timeout)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self.run_executable('python', args, **kwargs)
