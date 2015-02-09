# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import tempfile

import six

from .. import environment
from ..console import log
from .. import util


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
        super(Conda, self).__init__(conf)

    @classmethod
    def matches(self, python):
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
                    '--dry-run'], display_error=False)
            except util.ProcessError:
                return False
            else:
                return True

    @classmethod
    def get_environments(cls, conf, python):
        for configuration in environment.iter_configuration_matrix(conf.matrix):
            yield cls(conf, python, configuration)

    def setup(self):
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

    def install_requirements(self):
        if self._requirements_installed:
            return

        self.create()

        self.install('wheel')

        if self._requirements:
            # Install all the dependencies with a single conda command.
            # This ensures we get the versions requested, or an error
            # otherwise. It's also quicker than doing it one by one.
            args = ['install', '-p', self._path, '--yes']
            for key, val in six.iteritems(self._requirements):
                if val is not None:
                    args.append("{0}={1}".format(key, val))
                else:
                    args.append(key)
            self._run_executable('conda', args)

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
