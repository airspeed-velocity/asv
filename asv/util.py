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
import re
import subprocess

from .console import console


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


def check_call(args, error=True):
    """
    Runs the given command in a subprocess, raising
    subprocess.CalledProcessError if it fails.
    """
    check_output(args, error=error)


def check_output(args, error=True):
    """
    Runs the given command in a subprocess, returning the stdout
    content.  Raises subprocess.CalledProcessError if it fails.
    """
    p = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = p.communicate()
    retcode = p.poll()
    if retcode:
        if error:
            console.error("Running {0}".format(" ".join(args), stdout))
            raise subprocess.CalledProcessError(retcode, args)
    return stdout


def write_json(path, data):
    """
    Writes JSON to the given path, including indentation and sorting.
    """
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    with io.open(path, 'wb') as fd:
        json.dump(data, fd, indent=4, sort_keys=True)


def load_json(path):
    """
    Loads JSON to the given path, ignoring any C-style comments.
    """
    with io.open(path, 'rb') as fd:
        content = fd.read()

    content = re.sub(r'// .*', '', content, re.MULTILINE)
    return json.loads(content)
