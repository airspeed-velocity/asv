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
            "setup", help="Setup virtual environments",
            description="""Setup virtual environments for each
            combination of Python version and third-party requirement.
            This is called by the ``run`` command implicitly, and
            isn't generally required to be run on its own."""
        )

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        conf = Config.load(args.config)
        return cls.run(conf=conf)

    @classmethod
    def run(cls, conf):
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
