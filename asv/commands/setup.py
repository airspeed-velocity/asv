# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ..config import Config
from ..console import console
from .. import environment


class Setup(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "setup", help="Setup virtual environments")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        conf = Config.from_file(args.config)

        environments = list(
            environment.get_environments(
                conf.env_dir, conf.pythons, conf.matrix))

        with console.group("Creating virtualenvs...", color="green"):
            console.set_nitems(len(environments))
            for env in environments:
                console.step(env.name)
                with console.indent():
                    env.setup()

        return environments
