# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six
import virtualenv

from .console import console
from . import util


def get_configurations(pythons, matrix):
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
            yield (python, configuration)


def configuration_to_string(python, configuration):
    path = ["py{0}".format(python)]
    for key, val in six.iteritems(configuration):
        if val is not None:
            path.append(''.join([key, val]))
        else:
            path.append(key)
    return '-'.join(path)


class Environment(object):
    def __init__(self, executable, python, requirements):
        self.executable = executable
        self.virtualenv_path = virtualenv.__file__
        self.python = python
        self.requirements = requirements

        if not os.path.exists("env"):
            os.mkdir("env")

        self.path = os.path.join(
            "env",
            configuration_to_string(python, requirements))

        if not os.path.exists(self.path):
            self.setup()

        self.install_requirements()

    def setup(self):
        util.check_call([
            self.executable,
            self.virtualenv_path,
            '--no-site-packages',
            self.path])

    def install_requirements(self):
        for key, val in six.iteritems(self.requirements):
            if val is not None:
                self.install("{0}=={1}".format(key, val))
            else:
                self.install(key)

    @property
    def name(self):
        return configuration_to_string(self.python, self.requirements)

    def _run_executable(self, executable, args,
                        error=True):
        return util.check_output([
            os.path.join(self.path, 'bin', executable)] + args, error=error)

    def install(self, package):
        console.message("Installing {0}".format(package))
        self._run_executable('pip', ['install', package])

    def uninstall(self, package):
        console.message("Uninstalling {0}".format(package))
        self._run_executable('pip', ['uninstall', '-y', package], error=False)

    def run(self, args):
        return self._run_executable('python', args)
