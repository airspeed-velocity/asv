# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import multiprocessing

from ..config import Config
from ..console import console
from .. import environment


def _install_requirements(env):
    try:
        env.install_requirements()
    except:
        import traceback
        traceback.format_exc()
        raise


def _install_requirements_multiprocess(env):
    try:
        return _install_requirements(env)
    except:
        import traceback
        traceback.format_exc()
        raise


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

        parser.add_argument(
            "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
            help="""Build (but don't benchmark) in parallel.  The
            value is the number of CPUs to use, or if no number
            provided, use the number of cores on this machine. NOTE:
            parallel building is still considered experimental and may
            not work in all cases.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        conf = Config.load(args.config)
        return cls.run(conf=conf, parallel=args.parallel)

    @classmethod
    def run(cls, conf, parallel=-1):
        environments = list(
            environment.get_environments(
                conf.env_dir, conf.pythons, conf.matrix))

        if parallel <= 0:
            parallel = multiprocessing.cpu_count()

        with console.group("Creating virtualenvs...", color="green"):
            for env in environments:
                env.setup()

        with console.group("Installing dependencies...", color="green"):
            if parallel != 1:
                pool = multiprocessing.Pool(parallel)
                pool.map(_install_requirements_multiprocess, environments)
                pool.close()
            else:
                list(map(_install_requirements, environments))

        return environments
