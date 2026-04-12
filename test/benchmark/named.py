# SPDX-License-Identifier: BSD-3-Clause


class Suite:
    def named_method(self):
        return 0

    named_method.benchmark_name = 'custom.track_method'


def named_function():
    pass


named_function.benchmark_name = 'custom.time_function'
named_function.pretty_name = 'My Custom Function'


def track_custom_pretty_name():
    return 42


track_custom_pretty_name.pretty_name = 'this.is/the.answer'


class BaseSuite:
    def some_func(self):
        return 0


class OtherSuite:
    track_some_func = BaseSuite.some_func
