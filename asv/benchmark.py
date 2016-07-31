# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Manage a single benchmark and, when run from the commandline, report
its runtime to a file.
"""

# !!!!!!!!!!!!!!!!!!!! NOTE !!!!!!!!!!!!!!!!!!!!
# This file, unlike most others, must be compatible with as many
# versions of Python as possible and have no dependencies outside of
# the Python standard library.  This is the only bit of code from asv
# that is imported into the benchmarking process.

# Remove asv package directory from sys.path. This script file resides
# there although it's not part of the package, and Python puts it to
# sys.path[0] on start which can shadow other modules
import sys
sys.path.pop(0)

import copy
try:
    import cProfile as profile
except:
    profile = None
import ctypes
from ctypes.util import find_library
import errno
import imp
import inspect
import itertools
import json
import os
import pickle
import re
import textwrap
import timeit

# The best timer we can use is time.process_time, but it is not
# available in the Python stdlib until Python 3.3.  This is a ctypes
# backport for Pythons that don't have it.

try:
    from time import process_time
except ImportError:  # Python <3.3
    if sys.platform.startswith("linux"):
        CLOCK_PROCESS_CPUTIME_ID = 2  # time.h

        clockid_t = ctypes.c_int
        time_t = ctypes.c_long

        class timespec(ctypes.Structure):
            _fields_ = [
                ('tv_sec', time_t),         # seconds
                ('tv_nsec', ctypes.c_long)  # nanoseconds
            ]
        _clock_gettime = ctypes.CDLL(
            find_library('rt'), use_errno=True).clock_gettime
        _clock_gettime.argtypes = [clockid_t, ctypes.POINTER(timespec)]

        def process_time():
            tp = timespec()
            if _clock_gettime(CLOCK_PROCESS_CPUTIME_ID, ctypes.byref(tp)) < 0:
                err = ctypes.get_errno()
                msg = errno.errorcode[err]
                if err == errno.EINVAL:
                    msg += (
                        "The clk_id (4) specified is not supported on this system")
                raise OSError(err, msg)
            return tp.tv_sec + tp.tv_nsec * 1e-9

    elif sys.platform == 'darwin':
        RUSAGE_SELF = 0  # sys/resources.h

        time_t = ctypes.c_long
        suseconds_t = ctypes.c_int32

        class timeval(ctypes.Structure):
            _fields_ = [
                ('tv_sec', time_t),
                ('tv_usec', suseconds_t)
            ]

        class rusage(ctypes.Structure):
            _fields_ = [
                ('ru_utime', timeval),
                ('ru_stime', timeval),
                ('ru_maxrss', ctypes.c_long),
                ('ru_ixrss', ctypes.c_long),
                ('ru_idrss', ctypes.c_long),
                ('ru_isrss', ctypes.c_long),
                ('ru_minflt', ctypes.c_long),
                ('ru_majflt', ctypes.c_long),
                ('ru_nswap', ctypes.c_long),
                ('ru_inblock', ctypes.c_long),
                ('ru_oublock', ctypes.c_long),
                ('ru_msgsnd', ctypes.c_long),
                ('ru_msgrcv', ctypes.c_long),
                ('ru_nsignals', ctypes.c_long),
                ('ru_nvcsw', ctypes.c_long),
                ('ru_nivcsw', ctypes.c_long)
            ]

        _getrusage = ctypes.CDLL(find_library('c'), use_errno=True).getrusage
        _getrusage.argtypes = [ctypes.c_int, ctypes.POINTER(rusage)]

        def process_time():
            ru = rusage()
            if _getrusage(RUSAGE_SELF, ctypes.byref(ru)) < 0:
                err = ctypes.get_errno()
                msg = errno.errorcode[err]
                if err == errno.EINVAL:
                    msg += (
                        "The clk_id (0) specified is not supported on this system")
                raise OSError(err, msg)
            return float(ru.ru_utime.tv_sec + ru.ru_utime.tv_usec * 1e-6 +
                         ru.ru_stime.tv_sec + ru.ru_stime.tv_usec * 1e-6)

    else:
        # Fallback to default timer
        process_time = timeit.default_timer


def get_maxrss():
    # Fallback function, in case we don't have one that works on the
    # current platform
    return None

if sys.platform.startswith('win'):
    import ctypes
    import ctypes.wintypes

    SIZE_T = ctypes.c_size_t
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ('cb', ctypes.wintypes.DWORD),
            ('PageFaultCount', ctypes.wintypes.DWORD),
            ('PeakWorkingSetSize', SIZE_T),
            ('WorkingSetSize', SIZE_T),
            ('QuotaPeakPagedPoolUsage', SIZE_T),
            ('QuotaPagedPoolUsage', SIZE_T),
            ('QuotaPeakNonPagedPoolUsage', SIZE_T),
            ('QuotaNonPagedPoolUsage', SIZE_T),
            ('PagefileUsage', SIZE_T),
            ('PeakPagefileUsage', SIZE_T),
        ]

    GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
    GetCurrentProcess.argtypes = []
    GetCurrentProcess.restype = ctypes.wintypes.HANDLE

    GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
    GetProcessMemoryInfo.argtypes = (ctypes.wintypes.HANDLE,
                                     ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                                     ctypes.wintypes.DWORD)
    GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL

    def get_maxrss():
        proc_hnd = GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS()
        info = GetProcessMemoryInfo(proc_hnd, ctypes.byref(counters), ctypes.sizeof(counters))
        if info == 0:
            raise ctypes.WinError()
        return counters.PeakWorkingSetSize
else:
    try:
        import resource

        # POSIX
        if sys.platform == 'darwin':
            def get_maxrss():
                # OSX getrusage returns maxrss in bytes
                # https://developer.apple.com/library/mac/documentation/Darwin/Reference/ManPages/man2/getrusage.2.html
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        else:
            def get_maxrss():
                # Linux, *BSD return maxrss in kilobytes
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        pass


try:
    from importlib import import_module
except ImportError:  # For Python 2.6
    def _resolve_name(name, package, level):
        if not hasattr(package, 'rindex'):
            raise ValueError("'package' not set to a string")
        dot = len(package)
        for x in xrange(level, 1, -1):
            try:
                dot = package.rindex('.', 0, dot)
            except ValueError:
                raise ValueError("attempted relative import beyond top-level "
                                  "package")
        return "%s.%s" % (package[:dot], name)

    def import_module(name, package=None):
        if name.startswith('.'):
            if not package:
                raise TypeError("relative imports require the 'package' argument")
            level = 0
            for character in name:
                if character != '.':
                    break
                level += 1
            name = _resolve_name(name[level:], package, level)
        __import__(name)
        return sys.modules[name]


def _get_attr(source, name, ignore_case=False):
    if ignore_case:
        attrs = [getattr(source, key) for key in dir(source)
                 if key.lower() == name.lower()]

        if len(attrs) > 1:
            raise ValueError(
                "{0} contains multiple {1} functions.".format(
                    source.__name__, name))
        elif len(attrs) == 1:
            return attrs[0]
        else:
            return None
    else:
        return getattr(source, name, None)


def _get_all_attrs(sources, name, ignore_case=False):
    for source in sources:
        val = _get_attr(source, name, ignore_case=ignore_case)
        if val is not None:
            yield val


def _get_first_attr(sources, name, default, ignore_case=False):
    for val in _get_all_attrs(sources, name, ignore_case=ignore_case):
        return val
    return default


def get_benchmark_type_from_name(name):
    for bm_type in benchmark_types:
        if bm_type.name_regex.match(name):
            return bm_type
    return None


def get_setup_cache_key(func):
    if func is None:
        return None
    return '{0}:{1}'.format(inspect.getsourcefile(func),
                            inspect.getsourcelines(func)[1])


class Benchmark(object):
    """
    Represents a single benchmark.
    """
    # The regex of the name of function or method to be considered as
    # this type of benchmark.  The default in the base class, will
    # match nothing.
    name_regex = re.compile('^$')

    def __init__(self, name, func, attr_sources):
        name = name.split('.', 1)[1]
        self.name = name
        self.func = func
        self.pretty_name = getattr(func, "pretty_name", name)
        self._attr_sources = attr_sources
        self._setups = list(_get_all_attrs(attr_sources, 'setup', True))[::-1]
        self._teardowns = list(_get_all_attrs(attr_sources, 'teardown', True))
        self._setup_cache = _get_first_attr(attr_sources, 'setup_cache', None)
        self.setup_cache_key = get_setup_cache_key(self._setup_cache)
        self.setup_cache_timeout = _get_first_attr([self._setup_cache], "timeout", None)
        self.timeout = _get_first_attr(attr_sources, "timeout", 60.0)
        self.code = textwrap.dedent(inspect.getsource(self.func))
        self.type = "base"
        self.unit = "unit"

        self._redo_setup_next = False

        self._params = _get_first_attr(attr_sources, "params", [])
        self.param_names = _get_first_attr(attr_sources, "param_names", [])
        self._current_params = ()

        # Enforce params format
        try:
            self.param_names = [str(x) for x in list(self.param_names)]
        except ValueError:
            raise ValueError("%s.param_names is not a list of strings" % (name,))

        try:
            self._params = list(self._params)
        except ValueError:
            raise ValueError("%s.params is not a list" % (name,))

        if self._params and not isinstance(self._params[0], (tuple, list)):
            # Accept a single list for one parameter only
            self._params = [self._params]
        else:
            self._params = [[item for item in entry] for entry in self._params]

        if len(self.param_names) != len(self._params):
            self.param_names = self.param_names[:len(self._params)]
            self.param_names += ['param%d' % (k+1,) for k in range(len(self.param_names),
                                                                   len(self._params))]

        # Exported parameter representations
        self.params = [[repr(item) for item in entry] for entry in self._params]

    def set_param_idx(self, param_idx):
        try:
            self._current_params, = itertools.islice(
                itertools.product(*self._params),
                param_idx, param_idx + 1)
        except ValueError:
            raise ValueError(
                "Invalid benchmark parameter permutation index: %r" % (param_idx,))

    def insert_param(self, param):
        """
        Insert a parameter at the front of the parameter list.
        """
        self._current_params = tuple([param] + list(self._current_params))

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, self.name)

    @classmethod
    def from_function(cls, func):
        """
        Create a benchmark object from a free function.
        """
        module = inspect.getmodule(func)
        name = '.'.join(
            [module.__name__, func.__name__])
        return cls(name, func, [func, inspect.getmodule(func)])

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
        module = inspect.getmodule(klass)
        instance = klass()
        func = getattr(instance, method_name)
        name = '.'.join(
            [module.__name__, klass.__name__, method_name])
        return cls(name, func, [func, instance, module])

    @classmethod
    def from_name(cls, root, name, quick=False):
        """
        Create a benchmark from a fully-qualified benchmark name.

        Parameters
        ----------
        root : str
            Path to the root of a benchmark suite.

        name : str
            Fully-qualified name to a specific benchmark.
        """
        update_sys_path(root)

        def find_on_filesystem(root, parts, package):
            path = os.path.join(root, parts[0])
            if package:
                new_package = package + '.' + parts[0]
            else:
                new_package = parts[0]
            if os.path.isfile(path + '.py'):
                module = import_module(new_package)
                return find_in_module(module, parts[1:])
            elif os.path.isdir(path):
                return find_on_filesystem(
                    path, parts[1:], new_package)

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

        if '-' in name:
            try:
                name, param_idx = name.split('-', 1)
                param_idx = int(param_idx)
            except ValueError:
                raise ValueError("Benchmark id %r is invalid" % (name,))
        else:
            param_idx = None

        parts = name.split('.')

        benchmark = find_on_filesystem(
            root, parts, os.path.basename(root))

        if param_idx is not None:
            benchmark.set_param_idx(param_idx)

        if quick:
            class QuickBenchmarkAttrs:
                repeat = 1
                number = 1
            benchmark._attr_sources.insert(0, QuickBenchmarkAttrs)

        return benchmark

    def do_setup(self):
        try:
            for setup in self._setups:
                setup(*self._current_params)
        except NotImplementedError:
            # allow skipping test
            return True
        return False

    def redo_setup(self):
        if not self._redo_setup_next:
            self._redo_setup_next = True
            return
        self.do_teardown()
        self.do_setup()

    def do_teardown(self):
        for teardown in self._teardowns:
            teardown(*self._current_params)

    def do_setup_cache(self):
        if self._setup_cache is not None:
            return self._setup_cache()

    def do_run(self):
        return self.run(*self._current_params)

    def do_profile(self, filename=None):
        def method_caller():
            run(*params)

        if profile is None:
            raise RuntimeError("cProfile could not be imported")

        if filename is not None:
            if hasattr(method_caller, 'func_code'):
                code = method_caller.func_code
            else:
                code = method_caller.__code__

            self.redo_setup()

            profile.runctx(
                code, {'run': self.func, 'params': self._current_params},
                {}, filename)


class TimeBenchmark(Benchmark):
    """
    Represents a single benchmark for timing.
    """
    name_regex = re.compile(
        '^(Time[A-Z_].+)|(time_.+)$')

    def __init__(self, name, func, attr_sources):
        Benchmark.__init__(self, name, func, attr_sources)
        self.type = "time"
        self.unit = "seconds"
        self._attr_sources = attr_sources
        self._load_vars()

    def _load_vars(self):
        self.repeat = _get_first_attr(self._attr_sources, 'repeat', 0)
        self.number = int(_get_first_attr(self._attr_sources, 'number', 0))
        self.goal_time = _get_first_attr(self._attr_sources, 'goal_time', 2.0)
        self.timer = _get_first_attr(self._attr_sources, 'timer', process_time)

    def do_setup(self):
        result = Benchmark.do_setup(self)
        # For parameterized tests, setup() is allowed to change these
        self._load_vars()
        return result

    def run(self, *param):
        number = self.number
        repeat = self.repeat

        if repeat == 0:
            repeat = timeit.default_repeat

        if param:
            func = lambda: self.func(*param)
        else:
            func = self.func

        timer = timeit.Timer(
            stmt=func,
            setup=self.redo_setup,
            timer=self.timer)

        if number == 0:
            # determine number automatically so that
            # goal_time / 10 <= total time < goal_time
            number = 1
            for i in range(1, 10):
                if i > 1:
                    # increase number (don't rerun setup)
                    self._redo_setup_next = False
                    number *= 10

                timing = timer.timeit(number)
                if timing >= 5*self.goal_time and number == 1 and self.repeat == 0:
                    # very slow benchmark: use a default repeat value of 1
                    self.repeat = repeat = 1
                    break
                elif timing >= self.goal_time / 10.0:
                    break

            self.number = number

            # keep the timing from the run we already made
            repeat -= 1
            all_runs = [timing]
        else:
            all_runs = []

        if repeat > 0:
            all_runs.extend(timer.repeat(repeat, number))
        best = min(all_runs) / number
        return best


class MemBenchmark(Benchmark):
    """
    Represents a single benchmark for tracking the memory consumption
    of an object.
    """
    name_regex = re.compile(
        '^(Mem[A-Z_].+)|(mem_.+)$')

    def __init__(self, name, func, attr_sources):
        Benchmark.__init__(self, name, func, attr_sources)
        self.type = "memory"
        self.unit = "bytes"

    def run(self, *param):
        # We can't import asizeof directly, because we haven't loaded
        # the asv package in the benchmarking process.
        path = os.path.join(
            os.path.dirname(__file__), 'extern', 'asizeof.py')
        asizeof = imp.load_source('asizeof', path)

        obj = self.func(*param)

        sizeof2 = asizeof.asizeof([obj, obj])
        sizeofcopy = asizeof.asizeof([obj, copy.copy(obj)])

        return sizeofcopy - sizeof2


class PeakMemBenchmark(Benchmark):
    """
    Represents a single benchmark for tracking the peak memory consumption
    of the whole program.
    """
    name_regex = re.compile(
        '^(PeakMem[A-Z_].+)|(peakmem_.+)$')

    def __init__(self, name, func, attr_sources):
        Benchmark.__init__(self, name, func, attr_sources)
        self.type = "peakmemory"
        self.unit = "bytes"

    def run(self, *param):
        self.func(*param)
        return get_maxrss()


class TrackBenchmark(Benchmark):
    """
    Represents a single benchmark for tracking an arbitrary value.
    """
    name_regex = re.compile(
        '^(Track[A-Z_].+)|(track_.+)$')

    def __init__(self, name, func, attr_sources):
        Benchmark.__init__(self, name, func, attr_sources)
        self.type = _get_first_attr(attr_sources, "type", "track")
        self.unit = _get_first_attr(attr_sources, "unit", "unit")

    def run(self, *param):
        return self.func(*param)


# TODO: Support the creation of custom benchmark types


benchmark_types = [
    TimeBenchmark, MemBenchmark, PeakMemBenchmark, TrackBenchmark
]


class SpecificImporter(object):
    """
    Module importer that only allows loading a given module from the
    given path.

    Using this enables importing the asv benchmark suite without
    adding its parent directory to sys.path. The parent directory can
    in principle contain anything, including some version of the
    project module (common situtation if asv.conf.json is on project
    repository top level).
    """

    def __init__(self, name, root):
        self._name = name
        self._root = root

    def find_module(self, fullname, path=None):
        if fullname == self._name:
            return self
        return None

    def load_module(self, fullname):
        file, pathname, desc = imp.find_module(fullname, [self._root])
        return imp.load_module(fullname, file, pathname, desc)


def update_sys_path(root):
    sys.meta_path.insert(0, SpecificImporter(os.path.basename(root),
                                             os.path.dirname(root)))


def disc_class(klass):
    """
    Iterate over all benchmarks in a given class.

    For each method with a special name, yields a Benchmark
    object.
    """
    for key, val in inspect.getmembers(klass):
        bm_type = get_benchmark_type_from_name(key)
        if bm_type is not None and (inspect.isfunction(val) or inspect.ismethod(val)):
            yield bm_type.from_class_method(klass, key)


def disc_objects(module):
    """
    Iterate over all benchmarks in a given module, returning
    Benchmark objects.

    For each class definition, looks for any methods with a
    special name.

    For each free function, yields all functions with a special
    name.
    """
    for key, val in module.__dict__.items():
        if key.startswith('_'):
            continue
        if inspect.isclass(val):
            for benchmark in disc_class(val):
                yield benchmark
        elif inspect.isfunction(val):
            bm_type = get_benchmark_type_from_name(key)
            if bm_type is not None:
                yield bm_type.from_function(val)


def disc_files(root, package=''):
    """
    Iterate over all .py files in a given directory tree.
    """
    for filename in os.listdir(root):
        path = os.path.join(root, filename)
        if os.path.isfile(path):
            filename, ext = os.path.splitext(filename)
            if ext == '.py':
                module = import_module(package + filename)
                yield module
        elif os.path.isdir(path):
            for x in disc_files(path, package + filename + "."):
                yield x


def disc_benchmarks(root):
    """
    Discover all benchmarks in a given directory tree.
    """
    for module in disc_files(root, os.path.basename(root) + '.'):
        for benchmark in disc_objects(module):
            yield benchmark


def list_benchmarks(root, fp):
    """
    List all of the discovered benchmarks to fp as JSON.
    """
    update_sys_path(root)

    # Streaming of JSON back out to the master process

    fp.write('[')
    first = True
    for benchmark in disc_benchmarks(root):
        if not first:
            fp.write(', ')
        clean = dict(
            (k, v) for (k, v) in benchmark.__dict__.items()
            if isinstance(v, (str, int, float, list, dict, bool)) and not
               k.startswith('_'))
        json.dump(clean, fp, skipkeys=True)
        first = False
    fp.write(']')


def main_discover(args):
    benchmark_dir, result_file = args
    with open(result_file, 'w') as fp:
        list_benchmarks(benchmark_dir, fp)


def main_setup_cache(args):
    (benchmark_dir, benchmark_id) = args
    benchmark = Benchmark.from_name(benchmark_dir, benchmark_id)
    cache = benchmark.do_setup_cache()
    with open("cache.pickle", "wb") as fd:
        pickle.dump(cache, fd)


def main_run(args):
    (benchmark_dir, benchmark_id, quick, profile_path, result_file) = args
    quick = (quick == 'True')
    if profile_path == 'None':
        profile_path = None

    benchmark = Benchmark.from_name(
        benchmark_dir, benchmark_id, quick=quick)

    if benchmark.setup_cache_key is not None:
        with open("cache.pickle", "rb") as fd:
            cache = pickle.load(fd)
        if cache is not None:
            benchmark.insert_param(cache)

    skip = benchmark.do_setup()

    try:
        if skip:
            result = float('nan')
        else:
            result = benchmark.do_run()
            if profile_path is not None:
                benchmark.do_profile(profile_path)
    finally:
        benchmark.do_teardown()

    # Write the output value
    with open(result_file, 'w') as fp:
        json.dump(result, fp)


commands = {
    'discover': main_discover,
    'setup_cache': main_setup_cache,
    'run': main_run
}


if __name__ == '__main__':
    mode = sys.argv[1]
    args = sys.argv[2:]

    if mode in commands:
        commands[mode](args)
        sys.exit(0)
    else:
        sys.stderr.write("Unknown mode {0}\n".format(mode))
        sys.exit(1)
