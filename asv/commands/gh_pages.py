# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from .publish import Publish
from ..config import Config
from .. import util


class GithubPages(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "gh-pages",
            help="""
            Publish the results to Github pages.
            """,
            description="Publish the results to github pages")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        return cls.run(conf=Config.load(args.config))

    @classmethod
    def run(cls, conf):
        Publish.run(conf)

        os.environ['HTML_DIR'] = conf.html_dir

        util.check_call([
            os.path.join(os.path.dirname(__file__), 'gh_pages.sh')])
