# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Manage a single benchmark and, when run from the commandline, report
its runtime to stdout.
"""

# !!!!!!!!!!!!!!!!!!!! NOTE !!!!!!!!!!!!!!!!!!!!
# This file, unlike all others, must be compatible with as many
# versions of Python as possible and have no dependencies outside of
# the Python standard library.  This is the only bit of code from asv
# that is imported into the benchmarking process.

import imp
import inspect
import os
import re
import sys
import timeit


def _get_multi_name_attr(obj, name):
    attrs = [getattr(obj, key) for key in dir(obj)
             if key.lower() == name.lower()]

    if len(attrs) > 1:
        raise ValueError(
            "{0} contains multiple {1} functions.".format(
                obj.__name__, name))
    elif len(attrs) == 1:
        return attrs[0]
    else:
        return None


def get_benchmark_type_from_name(name):
    for bm_type in benchmark_types:
        if bm_type.name_regex.match(name):
            return bm_type
    return None


class Benchmark(object):
    """
    Represents a single benchmark.
    """
    # The regex of the name of function or method to be considered as
    # this type of benchmark.  The default in the base class, will
    # match nothing.
    name_regex = re.compile('^$')
    type = "base"
    unit = "unit"

    def __init__(self, name, func, attr_source):
        self.name = name
        self.func = func
        self.setup = _get_multi_name_attr(attr_source, 'setup')
        self.teardown = _get_multi_name_attr(attr_source, 'teardown')
        module = inspect.getmodule(attr_source)
        self.module_setup = _get_multi_name_attr(module, 'setup')
        self.module_teardown = _get_multi_name_attr(module, 'teardown')
        self.timeout = getattr(attr_source, "timeout", 60.0)
        self.attr_source = attr_source

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self.name)

    @classmethod
    def from_function(cls, func):
        """
        Create a benchmark object from a free function.
        """
        name = '.'.join(
            [inspect.getmodule(func).__name__, func.__name__])
        return cls(name, func, func)

    @classmethod
    def from_class_method(cls, klass, method_name):
        """
        Create a benchmark object from a method.

        Parameters
        ----------
        klass : type
            The class containing the method.

        method_name : str
            The name of the method.
        """
        name = '.'.join(
            [inspect.getmodule(klass).__name__, klass.__name__, method_name])
        instance = klass()
        func = getattr(instance, method_name)
        return cls(name, func, instance)

    @classmethod
    def from_name(cls, root, name):
        """
        Create a benchmark from a fully-qualified benchmark name.

        Parameters
        ----------
        root : str
            Path to the root of a benchmark suite.

        name : str
            Fully-qualified name to a specific benchmark.
        """
        def find_on_filesystem(root, parts, package):
            path = os.path.join(root, parts[0])
            if os.path.isfile(path + '.py'):
                module = imp.load_source(
                    package + '.' + parts[0], path + '.py')
                return find_in_module(module, parts[1:])
            elif os.path.isdir(path):
                return find_on_filesystem(
                    path, parts[1:], package + '.' + parts[0])

        def find_in_module(module, parts):
            attr = getattr(module, parts[0], None)

            if attr is not None:
                if inspect.isfunction(attr):
                    if len(parts) == 1:
                        bm_type = get_benchmark_type_from_name(parts[0])
                        if bm_type is not None:
                            return bm_type.from_function(attr)
                elif inspect.isclass(attr):
                    if len(parts) == 2:
                        bm_type = get_benchmark_type_from_name(parts[1])
                        if bm_type is not None:
                            return bm_type.from_class_method(attr, parts[1])

            raise ValueError(
                "Could not find benchmark '{0}'".format(name))

        parts = name.split('.')

        return find_on_filesystem(root, parts, '')

    @property
    def code(self):
        import textwrap
        return textwrap.dedent(inspect.getsource(self.func))

    def do_setup(self):
        if self.module_setup is not None:
            self.module_setup()

        if self.setup is not None:
            self.setup()

    def do_teardown(self):
        if self.module_teardown is not None:
            self.module_teardown()

        if self.teardown is not None:
            self.teardown()


class TimeBenchmark(Benchmark):
    """
    Represents a single benchmark for timing.
    """
    name_regex = re.compile(
        '^(Time[A-Z_].+)|(time_.+)$')
    type = "time"
    unit = "seconds"

    def __init__(self, name, func, attr_source):
        Benchmark.__init__(self, name, func, attr_source)
        self.goal_time = getattr(attr_source, 'goal_time', 2.0)
        self.timer = getattr(attr_source, 'timer', timeit.default_timer)
        self.repeat = getattr(attr_source, 'repeat', timeit.default_repeat)
        self.number = int(getattr(attr_source, 'number', 0))

    def run(self):
        number = self.number

        timer = timeit.Timer(
            stmt=self.func,
            timer=self.timer)

        if number == 0:
            # determine number automatically so that
            # goal_time / 10 <= total time < goal_time
            number = 1
            for i in range(1, 10):
                if timer.timeit(number) >= self.goal_time / 10.0:
                    break
                number *= 10

        all_runs = timer.repeat(self.repeat, number)
        best = min(all_runs) / number
        return best


class MemBenchmark(Benchmark):
    """
    Represents a single benchmark for tracking the memory consumption
    of an object.
    """
    name_regex = re.compile(
        '^(Mem[A-Z_].+)|(mem_.+)$')
    type = "memory"
    unit = "bytes"

    def __init__(self, name, func, attr_source):
        Benchmark.__init__(self, name, func, attr_source)

    def run(self):
        obj = self.func()
        return sys.getsizeof(obj)


class TrackBenchmark(Benchmark):
    """
    Represents a single benchmark for tracking an arbitrary value.
    """
    name_regex = re.compile(
        '^(Track[A-Z_].+)|(track_.+)$')

    def __init__(self, name, func, attr_source):
        Benchmark.__init__(self, name, func, attr_source)
        self.type = getattr(attr_source, "type", "track")
        self.unit = getattr(attr_source, "unit", "unit")

    def run(self):
        return self.func()


# TODO: Support the creation of custom benchmark types


benchmark_types = [
    TimeBenchmark, MemBenchmark, TrackBenchmark
]


if __name__ == '__main__':
    benchmark_dir = sys.argv[-2]
    benchmark_id = sys.argv[-1]

    benchmark = Benchmark.from_name(benchmark_dir, benchmark_id)
    benchmark.do_setup()
    result = benchmark.run()
    benchmark.do_teardown()

    # Write the numeric output value as the last line of the output.
    sys.stdout.write('\n')
    sys.stdout.write(str(result))
    sys.stdout.write('\n')
    sys.stdout.flush()
    # Not strictly necessary, but it's explicit about the successful
    # exit code that we want.
    sys.exit(0)
