# SPDX-License-Identifier: BSD-3-Clause

from .. import profiling, util


class SnakevizGui(profiling.ProfilerGui):
    name = 'snakeviz'
    description = "snakeviz https://jiffyclub.github.io/snakeviz/"

    @classmethod
    def is_available(cls):
        return util.has_command('snakeviz')

    @classmethod
    def open_profiler_gui(cls, profiler_file):
        command = util.which('snakeviz')

        return util.check_call([command, profiler_file], valid_return_codes=(0, -15), timeout=None)
