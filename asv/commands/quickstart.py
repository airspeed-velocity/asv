# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil

from six.moves import input as raw_input

from . import Command
from ..console import log


class Quickstart(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "quickstart", help="Create a new benchmarking suite",
            description="Creates a new bechmarking suite")

        parser.add_argument(
            "--dest", "-d", default=".",
            help="The destination directory for the new benchmarking "
            "suite")

        grp = parser.add_mutually_exclusive_group()
        grp.add_argument(
            "--top-level", action="store_true", dest="top_level", default=None,
            help="Benchmarks are on the top level of the project's repository")
        grp.add_argument(
            "--no-top-level", action="store_false", dest="top_level", default=None,
            help="Benchmarks are not in the project's repository top level")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        return cls.run(dest=args.dest, top_level=args.top_level)

    @classmethod
    def run(cls, dest=".", top_level=None):
        if top_level is None:
            while True:
                answer = raw_input("Is this the top level of your project repository? [y/n] ")
                if answer.lower()[:1] == "y":
                    top_level = True
                    break
                elif answer.lower()[:1] == "n":
                    top_level = False
                    break

        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'template')
        for entry in os.listdir(template_path):
            path = os.path.join(template_path, entry)
            dest_path = os.path.join(dest, entry)
            if os.path.exists(dest_path):
                log.info("Template content already exists.")
                log.info("Edit asv.conf.json to continue.")
                return 1

        for entry in os.listdir(template_path):
            path = os.path.join(template_path, entry)
            dest_path = os.path.join(dest, entry)
            if os.path.isdir(path):
                shutil.copytree(path, os.path.join(dest, entry))
            elif os.path.isfile(path):
                shutil.copyfile(path, os.path.join(dest, entry))

        if top_level:
            conf_file = os.path.join(dest, 'asv.conf.json')

            with open(conf_file, 'r') as f:
                conf = f.read()

            reps = [('"repo": "",', '"repo": ".",'),
                    ('// "env_dir": "env",', '"env_dir": ".asv/env",'),
                    ('// "results_dir": "results",', '"results_dir": ".asv/results",'),
                    ('// "html_dir": "html",', '"html_dir": ".asv/html",')]
            for src, dst in reps:
                conf = conf.replace(src, dst)

            with open(conf_file, 'w') as f:
                f.write(conf)

        log.info("Edit asv.conf.json to get started.")
