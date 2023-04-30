import copy
import cProfile as profile
import ctypes
import importlib.machinery
import importlib.util
import inspect
import itertools
import json
import os
import pickle
import re
import subprocess
import textwrap
import timeit
import time
import tempfile
import struct
import pkgutil
import traceback
import contextlib
import math
from pathlib import Path
from hashlib import sha256
from importlib import import_module
from collections import Counter
from time import process_time

def get_setup_cache_key(func):
    if func is None:
        return None

    module = inspect.getmodule(func)
    mname = ".".join(module.__name__.split('.', 1)[1:])
    if not mname:
        mname = inspect.getsourcefile(func)

    return f'{mname}:{inspect.getsourcelines(func)[1]}'

def get_source_code(items):
    """
    Extract source code of given items, and concatenate and dedent it.
    """
    sources = []
    prev_class_name = None

    for func in items:

        # custom source
        if hasattr(func, 'pretty_source'):
            src = textwrap.dedent(func.pretty_source).lstrip()
        # original source
        else:
            try:
                lines, _ = inspect.getsourcelines(func)
            except TypeError:
                continue

            if not lines:
                continue

            src = "\n".join(line.rstrip() for line in lines)
            src = textwrap.dedent(src)

        class_name = None
        if inspect.ismethod(func):
            # Add class name
            if hasattr(func, 'im_class'):
                class_name = func.im_class.__name__
            elif hasattr(func, '__qualname__'):
                names = func.__qualname__.split('.')
                if len(names) > 1:
                    class_name = names[-2]

        if class_name and prev_class_name != class_name:
            src = "class {0}:\n    {1}".format(
                class_name, src.replace("\n", "\n    "))
        elif class_name:
            src = "    " + src.replace("\n", "\n    ")

        sources.append(src)
        prev_class_name = class_name

    return "\n\n".join(sources).rstrip()

def _get_attr(source, name, ignore_case=False):
    if ignore_case:
        attrs = [getattr(source, key) for key in dir(source)
                 if key.lower() == name.lower()]

        if len(attrs) > 1:
            raise ValueError(f"{source.__name__} contains multiple {name} functions.")
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

class Benchmark:
    """
    Represents a single benchmark.
    """
    # The regex of the name of function or method to be considered as
    # this type of benchmark.  The default in the base class, will
    # match nothing.
    name_regex = re.compile('^$')

    def __init__(self, name, func, attr_sources):
        self.name = name
        self.func = func
        self.pretty_name = getattr(func, "pretty_name", None)
        self._attr_sources = attr_sources
        self._setups = list(_get_all_attrs(attr_sources, 'setup', True))[::-1]
        self._teardowns = list(_get_all_attrs(attr_sources, 'teardown', True))
        self._setup_cache = _get_first_attr(attr_sources, 'setup_cache', None)
        self.setup_cache_key = get_setup_cache_key(self._setup_cache)
        self.setup_cache_timeout = _get_first_attr([self._setup_cache], "timeout", None)
        self.timeout = _get_first_attr(attr_sources, "timeout", 60.0)
        self.code = get_source_code([self.func] + self._setups + [self._setup_cache])
        code_text = self.code.encode('utf-8')
        code_hash = sha256(code_text).hexdigest()
        self.version = str(_get_first_attr(attr_sources, "version", code_hash))
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
            raise ValueError(f"{name}.param_names is not a list of strings")

        try:
            self._params = list(self._params)
        except ValueError:
            raise ValueError(f"{name}.params is not a list")

        if self._params and not isinstance(self._params[0], (tuple, list)):
            # Accept a single list for one parameter only
            self._params = [self._params]
        else:
            self._params = [[item for item in entry] for entry in self._params]

        if len(self.param_names) != len(self._params):
            self.param_names = self.param_names[:len(self._params)]
            self.param_names += ['param%d' % (k + 1,) for k in range(len(self.param_names),
                                                                     len(self._params))]

        # Exported parameter representations
        self.params = [[_repr_no_address(item) for item in entry] for entry in self._params]
        for i, param in enumerate(self.params):
            if len(param) != len(set(param)):
                counter = Counter(param)
                dupe_dict = {name: 0 for name, count in counter.items() if count > 1}
                for j in range(len(param)):
                    name = param[j]
                    if name in dupe_dict:
                        param[j] = name + f' ({dupe_dict[name]})'
                        dupe_dict[name] += 1
                self.params[i] = param

    def set_param_idx(self, param_idx):
        try:
            self._current_params, = itertools.islice(
                itertools.product(*self._params),
                param_idx, param_idx + 1)
        except ValueError:
            raise ValueError(
                f"Invalid benchmark parameter permutation index: {param_idx!r}")

    def insert_param(self, param):
        """
        Insert a parameter at the front of the parameter list.
        """
        self._current_params = tuple([param] + list(self._current_params))

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name}>'

    def check(self, root):
        # Check call syntax (number of arguments only...)
        ok = True

        if self._params:
            self.set_param_idx(0)

        min_num_args = len(self._current_params)
        max_num_args = min_num_args

        if self.setup_cache_key is not None:
            ok = ok and check_num_args(root, self.name + ": setup_cache",
                                       self._setup_cache, 0)
            max_num_args += 1

        for setup in self._setups:
            ok = ok and check_num_args(root, self.name + ": setup",
                                       setup, min_num_args, max_num_args)

        ok = ok and check_num_args(root, self.name + ": call",
                                   self.func, min_num_args, max_num_args)

        for teardown in self._teardowns:
            ok = ok and check_num_args(root, self.name + ": teardown",
                                       teardown, min_num_args, max_num_args)

        return ok

    def do_setup(self):
        try:
            for setup in self._setups:
                setup(*self._current_params)
        except NotImplementedError as e:
            # allow skipping test
            print(f"asv: skipped: {e !r} ")
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
            run(*params)  # noqa:F821 undefined name  see #1020 Bug: run() function is not defined

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

class RayMemBenchmark(Benchmark):
    """
    A single benchmark for tracking the memory of an object with memray
    """

    name_regex = re.compile("^(Ray[A-Z_].+)|(ray_.+)$")

    def __init__(self, name, func, attr_sources):
        Benchmark.__init__(self, name, func, attr_sources)
        self.type = "memory"
        self.unit = "bytes"
        pass

    def run(self, *param):
        import memray
        from memray import FileReader
        import uuid

        u_id = uuid.uuid4()
        temp_dir = tempfile.gettempdir()
        tfile_loc = Path(f"{temp_dir}/{u_id}.bin")
        with memray.Tracker(
            destination=memray.FileDestination(tfile_loc, overwrite=True)
        ):
            self.func(*param)
        freader = FileReader(str(tfile_loc))
        return freader.metadata.peak_memory
