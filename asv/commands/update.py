# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from . import Command
from ..config import Config
from ..machine import Machine, MachineCollection
from ..results import Results


class Update(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "update", help="Update the results and config files "
            "to the current version",
            description="Update the results and config files "
            "to the current version")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        return cls.run(args.config)

    @classmethod
    def run(cls, config_path):
        MachineCollection.update()
        Config.update(config_path)

        conf = Config.load(config_path)

        for root, dirs, files in os.walk(conf.results_dir):
            for filename in files:
                path = os.path.join(root, filename)
                if filename == 'machine.json':
                    Machine.update(path)
                elif filename.endswith('.json'):
                    Results.update(path)
