# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import shutil

from ..environment import Environment
from ..console import log
from .. import util


class DumbEnv(Environment):
    """
    A dumb "environment" that doesn't actually do anything (for running
    with the current Python).
    """
    def __init__(self, *args):
        pass

    @classmethod
    def matches(self, executable):
        # This environment class is never selected implicitly.
        return False

    @property
    def name(self):
        """
        Get a name to uniquely identify this environment.
        """
        return "dumb"

    @property
    def requirements(self):
        return []

    @property
    def python(self):
        return "python"

    def _run_executable(self, executable, args, **kwargs):
        return util.check_output([executable] + args, **kwargs)

    def install_project(self, conf):
        return

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self._run_executable('python', args, **kwargs)
