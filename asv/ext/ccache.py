# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

"""
This plugin makes ccache more effective by making it sloppier and
removing debugging information from the generated files.
"""

# Contributed by @pv

import os
import sysconfig


def drop_g_flag(flags):
    """
    Drop -g from command line flags
    """
    if not flags:
        return flags
    return " ".join(
        x for x in flags.split() if x not in ('-g', '-g1', '-g2', '-g3'))


os.environ['CCACHE_SLOPPINESS'] = 'file_macro,time_macros'
os.environ['CCACHE_UNIFY'] = '1'
os.environ['CFLAGS'] = drop_g_flag(sysconfig.get_config_var('CFLAGS'))
os.environ['OPT'] = drop_g_flag(sysconfig.get_config_var('OPT'))
os.environ['LDSHARED'] = drop_g_flag(sysconfig.get_config_var('LDSHARED'))
