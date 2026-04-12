# SPDX-License-Identifier: BSD-3-Clause

from .. import profiling, util


class KCachegrindGui(profiling.ProfilerGui):
    name = 'kcachegrind'
    description = "kcachegrind through pyprof2calltree"

    @classmethod
    def is_available(cls):
        return util.has_command("kcachegrind") and util.has_command("pyprof2calltree")

    @classmethod
    def open_profiler_gui(cls, profiler_file):
        command = util.which("pyprof2calltree")

        return util.check_call([command, '-i', profiler_file, '-k'], timeout=None)
