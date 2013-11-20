# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Various low-level utilities.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import math
import os
try:
    import posix
except ImportError:
    posix = None
import subprocess
import threading
import time

import six

from .console import console
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


def which(filename):
    """
    Emulates the UNIX `which` command in Python.

    Raises a RuntimeError if no result is found.
    """
    locations = os.environ.get("PATH").split(os.pathsep)
    candidates = []
    for location in locations:
        candidate = os.path.join(location, filename)
        if os.path.isfile(candidate):
            candidates.append(candidate)
    if len(candidates) == 0:
        raise RuntimeError("Could not find '{0}' in PATH.".format(filename))
    return candidates[0]


class ProcessError(subprocess.CalledProcessError):
    def __init__(self, args, retcode, stdout, stderr):
        self.args = args
        self.retcode = retcode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return "Command '{0}' returned non-zero exit status {1}".format(
            ' '.join(self.args), self.retcode)


def check_call(args, error=True, timeout=60, dots=True):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.
    """
    check_output(args, error=error)


def check_output(args, error=True, timeout=60, dots=True):
    last_time = [time.time()]

    def read_stream(stream, lines):
        while True:
            line = stream.readline()
            if len(line) == 0:
                break
            lines.append(line)
            if dots:
                console.dot()
            last_time[0] = time.time()

    def wait():
        while True:
            if proc.poll():
                break
            time.sleep(0.01)

    kwargs = {}
    if posix:
        kwargs = {'close_fds': True}
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    proc = subprocess.Popen(args, **kwargs)

    stdout_lines = []
    stderr_lines = []
    # Setup all worker threads. By now the pipes have been created and
    # proc.stdout/proc.stderr point to open pipe objects.
    stdout_reader = threading.Thread(
        target=read_stream, args=(proc.stdout, stdout_lines))
    stderr_reader = threading.Thread(
        target=read_stream, args=(proc.stderr, stderr_lines))

    # Start all workers
    stdout_reader.start()
    stderr_reader.start()
    try:
        try:
            while True:
                if proc.poll() is not None:
                    break
                time.sleep(0.01)
                if time.time() - last_time[0] > timeout:
                    proc.terminate()
                    break
        except KeyboardInterrupt:
            proc.terminate()
            raise
    finally:
        proc.stdout.flush()
        proc.stderr.flush()
        stdout_reader.join()
        stderr_reader.join()

    stdout = b''.join(stdout_lines)
    stderr = b''.join(stderr_lines)
    stdout = stdout.decode('utf-8', 'replace')
    stderr = stderr.decode('utf-8', 'replace')

    retcode = proc.poll()
    if retcode:
        if error:
            console.error("Running {0}".format(" ".join(args)))
            console.add("STDOUT " + ("-" * 60) + '\n', 'red')
            console.add(stdout)
            console.add("STDERR " + ("-" * 60) + '\n', 'red')
            console.add(stderr)
            console.add(("-" * 67) + '\n', 'red')
            raise ProcessError(args, retcode, stdout, stderr)

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

    with io.open(path, 'wb') as fd:
        json.dump(data, fd, indent=4, sort_keys=True)


def load_json(path, api_version=None):
    """
    Loads JSON to the given path, ignoring any C-style comments.
    """
    path = os.path.abspath(path)

    with io.open(path, 'rb') as fd:
        content = fd.read()

    content = minify_json.json_minify(content)
    d = json.loads(content)

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
