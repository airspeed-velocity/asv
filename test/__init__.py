# Licensed under a 3-clause BSD style license - see LICENSE.rst

# Monkey-patch the machine name
from asv import machine
from asv.console import log

log.enable()

machine.Machine.hardcoded_machine_name = 'orangutan'
