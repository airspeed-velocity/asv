# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil

from ..console import console


class Quickstart(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "quickstart", help="Copies the files necessary for a new "
            "benchmarking project into the current directory.")

        parser.add_argument(
            "--dest", "-d", default=".",
            help="The destination directory for the new benchmarking "
            "project.")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        dest = args.dest

        template_path = os.path.join(
            os.path.dirname(__file__), '..', 'template')
        for entry in os.listdir(template_path):
            path = os.path.join(template_path, entry)
            if os.path.isdir(path):
                shutil.copytree(path, os.path.join(dest, entry))
            elif os.path.isfile(path):
                shutil.copyfile(path, os.path.join(dest, entry))

        console.message("Edit asv.conf.json to get started.", "green")
