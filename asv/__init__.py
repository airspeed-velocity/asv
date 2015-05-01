# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

if sys.version_info >= (3, 3):
    # OS X framework builds of Python 3.3 can not call other 3.3
    # virtualenvs as a subprocess because `__PYENV_LAUNCHER__` is
    # inherited.
    if os.environ.get('__PYVENV_LAUNCHER__'):
        os.unsetenv('__PYVENV_LAUNCHER__')

from ._version import __version__, __githash__, __release__

from . import plugin_manager
