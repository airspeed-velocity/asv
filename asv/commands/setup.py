# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import traceback

from . import Command
from ..console import log
from .. import environment
from .. import util

from . import common_args


def _create(env):
    with log.set_level(logging.WARN):
        env.create()


def _create_parallel(env):
    try:
        _create(env)
    except BaseException as exc:
        raise util.ParallelFailure(str(exc), exc.__class__, traceback.format_exc())


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

        common_args.add_parallel(parser)

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
            if parallel != 1:
                pool = multiprocessing.Pool(parallel)
                try:
                    pool.map(_create_parallel, environments)
                except util.ParallelFailure as exc:
                    exc.reraise()
                finally:
                    pool.close()
            else:
                list(map(_create, environments))

        return environments
