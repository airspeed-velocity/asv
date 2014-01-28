# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


from .. import profile
from .. import util


class RunSnakeRunGui(profile.ProfilerGui):
    name = 'runsnake'

    @classmethod
    def open_profiler_gui(cls, profiler_file):
        command = util.which('runsnake')

        util.check_call([command, profiler_file])
