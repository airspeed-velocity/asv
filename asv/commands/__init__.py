# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .machine import Machine
from .preview import Preview
from .publish import Publish
from .quickstart import Quickstart
from .run import Run
from .setup import Setup

# This list is ordered in order of average workflow
all_commands = [
    'Quickstart',
    'Machine',
    'Setup',
    'Run',
    'Publish',
    'Preview']
