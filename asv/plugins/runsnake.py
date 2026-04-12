# SPDX-License-Identifier: BSD-3-Clause

from .. import profiling, util


class RunSnakeRunGui(profiling.ProfilerGui):
    name = 'runsnake'
    description = "RunSnakeRun http://www.vrplumber.com/programming/runsnakerun/"

    @classmethod
    def is_available(cls):
        return util.has_command('runsnake')

    @classmethod
    def open_profiler_gui(cls, profiler_file):
        command = util.which('runsnake')

        return util.check_call([command, profiler_file], timeout=None)
