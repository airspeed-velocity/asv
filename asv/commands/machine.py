# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .. import machine


class Machine(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "machine", help="Define information about this machine")

        # TODO: Provide commandline arguments for everything

        parser.set_defaults(func=cls.run_from_args)

    @classmethod
    def run_from_args(cls, args):
        return cls.run()

    @classmethod
    def run(cls):
        machine.Machine.generate_machine_file(
            machine.Machine.get_machine_file_path())
