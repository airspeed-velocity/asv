# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

import six

from . import commands
from .config import Config
from .console import log
from .plugin_manager import plugin_manager


def main():
    plugin_manager.load_plugins_in_path(
        'asv.commands',
        os.path.dirname(commands.__file__))

    parser, subparsers = commands.make_argparser()

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    log.enable(args.verbose)

    conf = Config.load(args.config)

    # Use the path to the config file as the cwd for the remainder of
    # the run
    dirname = os.path.dirname(os.path.abspath(args.config))
    os.chdir(dirname)

    for plugin in conf.plugins:
        plugin_manager.import_plugin(plugin)

    try:
        args.func(conf, args)
    except RuntimeError as e:
        log.error(six.text_type(e))
        sys.exit(1)

    sys.stdout.write('\n')
