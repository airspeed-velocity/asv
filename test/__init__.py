# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from asv.console import log
log.enable()


# Monkey-patch the machine name
from asv import machine
machine.Machine.hardcoded_machine_name = 'orangutan'
