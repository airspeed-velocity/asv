# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six

from asv import machine


def test_machine(tmpdir):
    @staticmethod
    def get_machine_file_path():
        return six.text_type(tmpdir.join('asv-machine.json'))

    original_file_path = machine.MachineCollection.get_machine_file_path
    machine.MachineCollection.get_machine_file_path = get_machine_file_path

    try:
        m = machine.Machine.load(
            interactive=False,
            machine="foo",
            os="BeOS",
            arch="MIPS",
            cpu="10 MHz",
            ram="640k")

        m = machine.Machine.load(interactive=False)

        assert m.machine == 'foo'
        assert m.os == 'BeOS'
        assert m.arch == 'MIPS'
        assert m.cpu == '10 MHz'
        assert m.ram == '640k'
    finally:
        machine.MachineCollection.get_machine_file_path = original_file_path
