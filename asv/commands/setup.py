# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ..config import Config
from ..console import console
from .. import environment
from .. import util


class Setup(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "setup", help="Setup virtual environments")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        conf = Config.from_file(args.config)

        configurations = list(
            environment.get_configurations(conf.pythons, conf.matrix))

        environments = []

        with console.group("Creating virtualenvs...", color="green"):
            console.set_nitems(len(configurations))
            for python, configuration in configurations:
                config_name = environment.configuration_to_string(
                    python, configuration)

                executables = util.which("python{0}".format(python))
                if len(executables) == [0]:
                    console.warning(
                        "Skipping {0}: no executable found".format(config_name))
                    continue
                executable = executables[0]

                console.step(config_name)
                with console.indent():
                    environments.append(
                        environment.Environment(executable, python, configuration))

        return environments
