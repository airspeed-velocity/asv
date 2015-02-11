# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging

from . import Command
from ..console import log
from .. import environment
from ..repo import get_repo
from .. import util


def _install_requirements(env):
    try:
        with log.set_level(logging.WARN):
            env.install_requirements()
    except:
        import traceback
        traceback.print_exc()
        raise


def _install_requirements_multiprocess(env):
    try:
        return _install_requirements(env)
    except:
        import traceback
        traceback.print_exc()
        raise


class Setup(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "setup", help="Setup virtual environments",
            description="""Setup virtual environments for each
            combination of Python version and third-party requirement.
            This is called by the ``run`` command implicitly, and
            isn't generally required to be run on its own."""
        )

        parser.add_argument(
            "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
            help="""Build (but don't benchmark) in parallel.  The
            value is the number of CPUs to use, or if no number
            provided, use the number of cores on this machine.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf, parallel=args.parallel)

    @classmethod
    def run(cls, conf, parallel=-1):
        environments = list(environment.get_environments(conf))

        if all(isinstance(env, environment.ExistingEnvironment) for env in environments):
            # Nothing to do, so don't print anything
            return environments

        parallel, multiprocessing = util.get_multiprocessing(parallel)

        log.info("Creating environments")
        with log.indent():
            for env in environments:
                env.create()

        log.info("Installing dependencies")
        with log.indent():
            if parallel != 1:
                pool = multiprocessing.Pool(parallel)
                pool.map(_install_requirements_multiprocess, environments)
                pool.close()
            else:
                list(map(_install_requirements, environments))

        return environments
