# SPDX-License-Identifier: BSD-3-Clause

# Monkey-patch the machine name
from asv import machine
from asv.console import log

log.enable()

machine.Machine.hardcoded_machine_name = 'orangutan'
