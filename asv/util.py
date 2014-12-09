# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Various low-level utilities.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import math
import os
import select
import subprocess
import struct
import sys
import time

try:
    from select import PIPE_BUF
except ImportError:
    # PIPE_BUF is not available on Python 2.6
    PIPE_BUF = os.pathconf('.', os.pathconf_names['PC_PIPE_BUF'])

import six
from six.moves import xrange

from .console import log
from .extern import minify_json


def human_file_size(size):
    """
    Returns a human-friendly string representing a file size
    that is 2-4 characters long.

    For example, depending on the number of bytes given, can be one
    of::

        256b
        64k
        1.1G

    Parameters
    ----------
    size : int
        The size of the file (in bytes)

    Returns
    -------
    size : str
        A human-friendly representation of the size of the file
    """
    size = float(size)

    suffixes = ' kMGTPEH'
    if size == 0:
        num_scale = 0
    else:
        num_scale = int(math.floor(math.log(size) / math.log(1000)))
    if num_scale > 7:
        suffix = '?'
    else:
        suffix = suffixes[num_scale]
    num_scale = int(math.pow(1000, num_scale))
    value = size / num_scale
    str_value = str(value)
    if str_value[2] == '.':
        str_value = str_value[:2]
    else:
        str_value = str_value[:3]
    return "{0:>3s}{1}".format(str_value, suffix)


def human_time(seconds):
    """
    Returns a human-friendly time string that is always exactly 6
    characters long.

    Depending on the number of seconds given, can be one of::

        1w 3d
        2d 4h
        1h 5m
        1m 4s
          15s

    Will be in color if console coloring is turned on.

    Parameters
    ----------
    seconds : int
        The number of seconds to represent

    Returns
    -------
    time : str
        A human-friendly representation of the given number of seconds
        that is always exactly 6 characters.
    """
    units = [
        ('ns', 0.000000001),
        ('μs', 0.000001),
        ('ms', 0.001),
        ('s', 1),
        ('m', 60),
        ('h', 60 * 60),
        ('d', 60 * 60 * 24),
        ('w', 60 * 60 * 24 * 7),
        ('y', 60 * 60 * 24 * 7 * 52),
        ('C', 60 * 60 * 24 * 7 * 52 * 100)
    ]

    seconds = float(seconds)

    for i in xrange(len(units) - 1):
        if seconds < units[i+1][1]:
            return "{0:.02f}{1}".format(seconds / units[i][1], units[i][0])
    return '~0'


def human_value(value, unit):
    """
    Formats a value in a given unit in a human friendly way.

    Parameters
    ----------
    value : anything
        The value to format

    unit : str
        The unit the value is in.  Currently understands `seconds` and `bytes`.
    """
    if isinstance(value, (int, float)):
        if unit == 'seconds':
            display = human_time(value)
        elif unit == 'bytes':
            display = human_file_size(value)
        else:
            display = json.dumps(value)
    else:
        display = json.dumps(value)

    return display


def which(filename):
    """
    Emulates the UNIX `which` command in Python.

    Raises a RuntimeError if no result is found.
    """
    locations = os.environ.get("PATH").split(os.pathsep)
    candidates = []
    for location in locations:
        candidate = os.path.join(location, filename)
        if os.path.isfile(candidate) or os.path.islink(candidate):
            candidates.append(candidate)
    if len(candidates) == 0:
        raise RuntimeError("Could not find '{0}' in PATH".format(filename))
    return candidates[0]


def has_command(filename):
    """
    Returns `True` if the commandline utility exists.
    """
    try:
        which(filename)
    except RuntimeError:
        return False
    else:
        return True


class ProcessError(subprocess.CalledProcessError):
    def __init__(self, args, retcode, stdout, stderr):
        self.args = args
        self.retcode = retcode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return "Command '{0}' returned non-zero exit status {1}".format(
            ' '.join(self.args), self.retcode)


def check_call(args, error=True, timeout=60, dots=True, display_error=True,
               shell=False, env=None):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.

    See `check_output` for parameters.
    """
    check_output(
        args, error=error, timeout=timeout, dots=dots,
        display_error=display_error, shell=shell, env=env)


def check_output(args, error=True, timeout=120, dots=True, display_error=True,
                 shell=False, return_stderr=False, env=None):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.  Returns stdout as a string on success.

    Parameters
    ----------
    error : bool, optional
        When `True` (default) raise a ProcessError if the subprocess
        returns an error code.

    timeout : number, optional
        Kill the process if it lasts longer than `timeout` seconds.

    dots : bool, optional
        If `True` (default) write a dot to the console to show
        progress as the subprocess outputs content.  May also be
        a callback function to call (with no arguments) to indicate
        progress.

    display_error : bool, optional
        If `True` (default) display the stdout and stderr of the
        subprocess when the subprocess returns an error code.

    shell : bool, optional
        If `True`, run the command through the shell.  Default is
        `False`.
    env : dict, optional
        Specify environment variables for the subprocess.
    """
    def get_content(header=None):
        content = []
        if header is not None:
            content.append(header)
        content.extend([
            'STDOUT -------->',
            stdout[:-1],
            'STDERR -------->',
            stderr[:-1]
        ])

        return '\n'.join(content)

    log.debug("Running '{0}'".format(' '.join(args)))

    proc = subprocess.Popen(
        args,
        close_fds=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell)

    last_dot_time = time.time()
    stdout_chunks = []
    stderr_chunks = []
    try:
        fds = {
            proc.stdout.fileno(): stdout_chunks,
            proc.stderr.fileno(): stderr_chunks
            }

        while proc.poll() is None:
            rlist, wlist, xlist = select.select(
                list(fds.keys()), [], [], timeout)
            if len(rlist) == 0:
                # We got a timeout
                proc.terminate()
                break
            for f in rlist:
                output = os.read(f, PIPE_BUF)
                fds[f].append(output)
            if dots and time.time() - last_dot_time > 0.5:
                if dots is True:
                    log.dot()
                elif dots:
                    dots()
                last_dot_time = time.time()
    except KeyboardInterrupt:
        proc.terminate()
        raise

    proc.stdout.flush()
    proc.stderr.flush()
    stdout_chunks.append(proc.stdout.read())
    stderr_chunks.append(proc.stderr.read())

    stdout = b''.join(stdout_chunks).decode('utf-8', 'replace')
    stderr = b''.join(stderr_chunks).decode('utf-8', 'replace')

    retcode = proc.wait()
    if retcode and error:
        header = 'Error running {0}'.format(' '.join(args))
        if display_error:
            log.error(get_content(header))
        else:
            if log.is_debug_enabled():
                log.debug(get_content(header))
        raise ProcessError(args, retcode, stdout, stderr)
    elif log.is_debug_enabled():
        log.debug(get_content())

    if return_stderr:
        return stderr
    else:
        return stdout


def write_json(path, data, api_version=None):
    """
    Writes JSON to the given path, including indentation and sorting.
    """
    path = os.path.abspath(path)
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    if api_version is not None:
        data['version'] = api_version

    with open(path, 'w') as fd:
        json.dump(data, fd, indent=4, sort_keys=True)


def load_json(path, api_version=None):
    """
    Loads JSON to the given path, ignoring any C-style comments.
    """
    path = os.path.abspath(path)

    with open(path, 'r') as fd:
        content = fd.read()

    content = minify_json.json_minify(content)
    content = content.replace(",]", "]")
    content = content.replace(",}", "}")
    try:
        d = json.loads(content)
    except ValueError as e:
        raise ValueError(
            "Error parsing JSON in file '{0}': {1}".format(
                path, six.text_type(e)))

    if api_version is not None:
        if 'version' in d:
            if d['version'] < api_version:
                raise RuntimeError(
                    "{0} is stored in an old file format.  Run "
                    "`asv update` to update it.".format(path))
            elif d['version'] > api_version:
                raise RuntimeError(
                    "{0} is stored in a format that is newer than "
                    "what this version of asv understands.  Update "
                    "asv to use this file.".format(path))

            del d['version']
        else:
            raise RuntimeError(
                "No version specified in {0}.".format(path))

    return d


def update_json(cls, path, api_version):
    """
    Perform JSON file format updates.

    Parameters
    ----------
    cls : object
        Object containing methods update_to_X which updates
        the given JSON tree from version X-1 to X.

    path : str
        Path to JSON file

    api_version : int
        The current API version
    """
    d = load_json(path)
    if 'version' not in d:
        raise RuntimeError(
            "No version specified in {0}.".format(path))

    if d['version'] < api_version:
        for x in six.moves.xrange(d['version'] + 1, api_version):
            d = getattr(cls, 'update_to_{0}'.format(x), lambda x: x)(d)
        write_json(path, d, api_version)
    elif d['version'] > api_version:
        raise RuntimeError(
            "version of {0} is newer than understood by this version of "
            "asv. Upgrade asv in order to use or add to these results.")


def iter_chunks(s, n):
    """
    Iterator that returns elements from s in chunks of size n.
    """
    chunk = []
    for x in s:
        chunk.append(x)
        if len(chunk) == n:
            yield chunk
            chunk = []
    if len(chunk):
        yield chunk


def get_multiprocessing(parallel):
    """
    If parallel indicates that we want to do multiprocessing,
    imports the multiprocessing module and sets the parallel
    value accordingly.
    """
    if parallel != 1:
        import multiprocessing
        if parallel <= 0:
            parallel = multiprocessing.cpu_count()
        return parallel, multiprocessing
    return parallel, None


def iter_subclasses(cls):
    """
    Returns all subclasses of a class.
    """
    for x in cls.__subclasses__():
        yield x
        for y in iter_subclasses(x):
            yield y


def hash_equal(a, b):
    """
    Returns `True` if a and b represent the same commit hash.
    """
    min_len = min(len(a), len(b))
    return a.lower()[:min_len] == b.lower()[:min_len]


def get_cpu_info():
    """
    Gets a human-friendly description of this machine's CPU.

    Returns '' if it can't be obtained.
    """
    if sys.platform.startswith('linux'):
        with open("/proc/cpuinfo", "rb") as fd:
            lines = fd.readlines()
        for line in lines:
            if b':' in line:
                key, val = line.split(b':', 1)
                key = key.strip()
                val = val.strip()
                if key == b'model name':
                    return val.decode('ascii')
    elif sys.platform.startswith('darwin'):
        sysctl = which('sysctl')
        return check_output([sysctl, '-n', 'machdep.cpu.brand_string']).strip()
    return ''


def get_memsize():
    """
    Returns the amount of physical memory in this machine.

    Returns '' if it can't be obtained.
    """
    if sys.platform.startswith('linux'):
        with open("/proc/meminfo", "rb") as fd:
            lines = fd.readlines()
        for line in lines:
            if b':' in line:
                key, val = line.split(b':', 1)
                key = key.strip()
                val = val.strip()
                if key == b'MemTotal':
                    return int(val.split()[0])
    elif sys.platform.startswith('darwin'):
        sysctl = which('sysctl')
        return int(check_output([sysctl, '-n', 'hw.memsize']).strip())
    return ''


def _get_terminal_size_fallback():
    """
    Returns a tuple (height, width) containing the height and width of
    the terminal.  Fallback for when sys.get_terminal_size() doesn't
    exist or fails.
    """
    try:
        # Unix-specific code
        import fcntl
        import termios
        s = struct.pack(str("HHHH"), 0, 0, 0, 0)
        x = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, s)
        (lines, width, xpixels, ypixels) = struct.unpack(str("HHHH"), x)
        if lines > 12:
            lines -= 6
        if width > 10:
            width -= 1
        return (lines, width)
    except:
        # Fall back on environment variables, or if not set, (25, 80)
        try:
            return (int(os.environ.get('LINES')),
                    int(os.environ.get('COLUMNS')))
        except TypeError:
            return 25, 80


def get_terminal_width():
    """
    Return the terminal width, or an estimate thereof.
    """
    try:
        # Python 3.3 and higher: this works under Windows and Unix
        return os.get_terminal_size().columns
    except (AttributeError, OSError):
        return _get_terminal_size_fallback()[1]
