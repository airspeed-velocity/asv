# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from ..commands import Command
from ..commands.publish import Publish
from ..console import log
from .. import util


class GithubPages(Command):
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
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf)

    @classmethod
    def run(cls, conf):
        # TODO: For transactional integrity, we probably need to check
        # out the repo in a temporary directory

        Publish.run(conf)

        os.environ['HTML_DIR'] = conf.html_dir

        git = util.which('git')

        # Get the current branch name
        current_branch = util.check_output(
            [git, 'rev-parse', '--abbrev-ref', 'HEAD']).strip()
        if current_branch == 'gh-pages':
            util.check_call([git, 'checkout', 'master'])

        # Create a new "orphaned" branch -- we don't need history for
        # the built products
        util.check_call([git, 'branch', '-D', 'gh-pages'],
                        error=False, display_error=False)
        util.check_call([git, 'checkout', '--orphan', 'gh-pages'])

        # We need to tell github this is not a Jekyll document
        with open('.nojekyll', 'wb') as fd:
            fd.write(b'\n')
        util.check_call([git, 'add', '.nojekyll'])

        util.check_call([git, 'add', '-f', 'html'])
        util.check_call(["git mv html/* ."], shell=True)
        util.check_call([git, 'commit', '-m', 'Generated from sources'])

        log.info("Updating gh-pages branch on github")
        util.check_call([git, 'push', '-f', 'origin', 'gh-pages'])
        util.check_call([git, 'checkout', current_branch])
