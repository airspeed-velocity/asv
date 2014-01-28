# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


class ProfilerGui(object):
    """
    A base class to define a Profiler GUI that is available through
    the ``asv profile`` command.
    """
    name = None

    @classmethod
    def open_profiler_gui(cls, profiler_file):
        """
        Open the profiler GUI to display the results in the given
        profiler file.
        """
        raise NotImplementedError()
