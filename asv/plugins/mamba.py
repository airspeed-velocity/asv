# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

from .. import util
from .conda import Conda



class Mamba(Conda):
    """
    Manage an environment using mamba.

    Dependencies are installed using ``mamba``.  The benchmarked
    project is installed using ``pip`` (since ``mamba`` doesn't have a
    method to install from an arbitrary ``setup.py``).
    """
    tool_name = "mamba"
    _matches_cache = {}

    @staticmethod
    def _find_executable():
        """
        Find the mamba executable robustly across mamba versions.

        Returns
        -------
        mamba : str
            Path to the mamba executable.

        Raises
        ------
        IOError
            If the executable cannot be found in the PATH.
        """
        return util.which('mamba')

_find_mamba = Mamba._find_executable
