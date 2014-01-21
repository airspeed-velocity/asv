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

try:
    from select import PIPE_BUF
except ImportError:
    # PIPE_BUF is not available on Python 2.6
    PIPE_BUF = os.pathconf('.', os.pathconf_names['PC_PIPE_BUF'])

import six
from six.moves import xrange

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


def check_call(args, error=True, timeout=60, dots=True, display_error=True,
               shell=False):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.

    See `check_output` for parameters.
    """
    check_output(
        args, error=error, timeout=timeout, dots=dots,
        display_error=display_error, shell=shell)


def check_output(args, error=True, timeout=120, dots=True, display_error=True,
                 shell=False):
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
        progress as the subprocess outputs content.

    display_error : bool, optional
        If `True` (default) display the stdout and stderr of the
        subprocess when the subprocess returns an error code.

    shell : bool, optional
        If `True`, run the command through the shell.  Default is
        `False`.
    """
    proc = subprocess.Popen(
        args,
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell)

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
            if dots:
                console.dot()
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
    if retcode:
        if error:
            if display_error:
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
