# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
A set of utilities for writing output to the console.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import os
import warnings
import codecs
import contextlib
import locale
import logging
import sys
import textwrap

import six
from six.moves import xrange, input

if os.name == 'nt':
    try:
        from colorama import init
        init()
    except ImportError:
        warnings.warn('the colorama package is required for terminal color on Windows')


def isatty(file):
    """
    Returns `True` if `file` is a tty.

    Most built-in Python file-like objects have an `isatty` member,
    but some user-defined types may not, so this assumes those are not
    ttys.
    """
    if hasattr(file, 'isatty'):
        return file.isatty()
    return False


def _decode_preferred_encoding(s):
    """
    Decode the supplied byte string using the preferred encoding for
    the locale (`locale.getpreferredencoding`) or, if the default
    encoding is invalid, fall back first on utf-8, then on latin-1 if
    the message cannot be decoded with utf-8.
    """

    if six.PY3 and isinstance(s, bytes):
        enc = locale.getpreferredencoding()
        try:
            try:
                return s.decode(enc)
            except LookupError:
                enc = 'utf-8'
            return s.decode(enc)
        except UnicodeDecodeError:
            return s.decode('latin-1', 'replace')
    return s


def _color_text(text, color):
    """
    Returns a string wrapped in ANSI color codes for coloring the
    text in a terminal::

        colored_text = color_text('Here is a message', 'blue')

    This won't actually effect the text until it is printed to the
    terminal.

    Parameters
    ----------
    text : str
        The string to return, bounded by the color codes.
    color : str
        An ANSI terminal color name. Must be one of:
        black, red, green, brown, blue, magenta, cyan, lightgrey,
        default, darkgrey, lightred, lightgreen, yellow, lightblue,
        lightmagenta, lightcyan, white, or '' (the empty string).
    """
    color_mapping = {
        'black': '0;30',
        'red': '0;31',
        'green': '0;32',
        'brown': '0;33',
        'blue': '0;34',
        'magenta': '0;35',
        'cyan': '0;36',
        'lightgrey': '0;37',
        'default': '0;39',
        'darkgrey': '1;30',
        'lightred': '1;31',
        'lightgreen': '1;32',
        'yellow': '1;33',
        'lightblue': '1;34',
        'lightmagenta': '1;35',
        'lightcyan': '1;36',
        'white': '1;37'}
    color_code = color_mapping.get(color, '0;39')
    return '\033[{0}m{1}\033[0m'.format(color_code, text)


if os.name == 'nt' and 'colorama' not in sys.modules:
    # :(
    def _color_text(text, color):
        return text


def _write_with_fallback(s, write, fileobj):
    """
    Write the supplied string with the given write function like
    ``write(s)``, but use a writer for the locale's preferred encoding
    in case of a UnicodeEncodeError.  Failing that attempt to write
    with 'utf-8' or 'latin-1'.
    """
    try:
        write(s)
        return write
    except UnicodeEncodeError:
        # Let's try the next approach...
        pass

    enc = locale.getpreferredencoding()
    try:
        Writer = codecs.getwriter(enc)
    except LookupError:
        Writer = codecs.getwriter('utf-8')

    f = Writer(fileobj)
    write = f.write

    try:
        write(s)
        return write
    except UnicodeEncodeError:
        Writer = codecs.getwriter('latin-1')
        f = Writer(fileobj)
        write = f.write

    # If this doesn't work let the exception bubble up; I'm out of ideas
    try:
        write(s)
        return write
    except UnicodeEncodeError:
        write(s.encode('ascii', 'replace'))
        return write


def color_print(*args, **kwargs):
    """
    Prints colors and styles to the terminal uses ANSI escape
    sequences.

    ::

       color_print('This is the color ', 'default', 'GREEN', 'green')

    Parameters
    ----------
    positional args : str
        The positional arguments come in pairs (*msg*, *color*), where
        *msg* is the string to display and *color* is the color to
        display it in.

        *color* is an ANSI terminal color name.  Must be one of:
        black, red, green, brown, blue, magenta, cyan, lightgrey,
        default, darkgrey, lightred, lightgreen, yellow, lightblue,
        lightmagenta, lightcyan, white, or '' (the empty string).

    file : writeable file-like object, optional
        Where to write to.  Defaults to `sys.stdout`.  If file is not
        a tty (as determined by calling its `isatty` member, if one
        exists), no coloring will be included.

    end : str, optional
        The ending of the message.  Defaults to ``\\n``.  The end will
        be printed after resetting any color or font state.
    """

    file = kwargs.get('file', sys.stdout)

    end = kwargs.get('end', '')

    write = file.write
    if isatty(file):
        for i in xrange(0, len(args), 2):
            msg = args[i]
            if i + 1 == len(args):
                color = ''
            else:
                color = args[i + 1]

            if color:
                msg = _color_text(msg, color)
            msg = _decode_preferred_encoding(msg)
            write = _write_with_fallback(msg, write, file)

        write(end)
    else:
        for i in xrange(0, len(args), 2):
            msg = args[i]
            msg = _decode_preferred_encoding(msg)
            write = _write_with_fallback(msg, write, file)
        write(end)


def get_answer_default(prompt, default):
    print("{0} [{1}]: ".format(prompt, default), end='')
    x = input()
    if x.strip() == '':
        return default
    return x


def truncate_left(s, l):
    if len(s) > l:
        return '...' + s[-(l - 3):]
    else:
        return s


class Log(object):
    def __init__(self):
        self._indent = 1
        self._total = 0
        self._count = 0
        self._logger = logging.getLogger()
        self._needs_newline = False

    def _stream_formatter(self, record):
        '''
        The formatter for standard output
        '''
        if self._needs_newline:
            color_print('\n')
        parts = record.msg.split('\n', 1)
        first_line = parts[0]
        if len(parts) == 1:
            rest = None
        else:
            rest = parts[1]

        if self._total:
            color_print('[{0:6.02f}%] '.format(
                (float(self._count) / self._total) * 100.0))

        color_print('·' * self._indent)
        color_print(' ')

        if record.levelno < logging.DEBUG:
            color = 'default'
        elif record.levelno < logging.INFO:
            color = 'default'
        elif record.levelno < logging.WARN:
            if self._indent == 1:
                color = 'green'
            elif self._indent == 2:
                color = 'blue'
            else:
                color = 'default'
        elif record.levelno < logging.ERROR:
            color = 'brown'
        else:
            color = 'red'

        indent = self._indent + 11
        spaces = ' ' * indent
        color_print(first_line, color)
        if rest is not None:
            color_print('\n')
            detail = textwrap.dedent(rest)
            for line in detail.split('\n'):
                color_print(spaces)
                color_print(line)
                color_print('\n')

        self._needs_newline = True
        sys.stdout.flush()

    @contextlib.contextmanager
    def indent(self):
        """
        A context manager to increase the indentation level.
        """
        self._indent += 1
        yield
        self._indent -= 1

    def dot(self):
        if isatty(sys.stdout):
            color_print('.', 'darkgrey')
            sys.stdout.flush()

    def set_nitems(self, n):
        """
        Set the number of items in a lengthy process.  Each of these
        steps should be incremented through using `step`.
        """
        self._total = n

    def step(self):
        """
        Write that a step has been completed.  A percentage is
        displayed along with it.
        """
        self._count += 1

    def enable(self, verbose=False):
        sh = logging.StreamHandler()
        sh.emit = self._stream_formatter
        self._logger.addHandler(sh)
        if verbose:
            self._logger.setLevel(logging.DEBUG)
        else:
            self._logger.setLevel(logging.INFO)

    @contextlib.contextmanager
    def set_level(self, level):
        orig_level = self._logger.level
        self._logger.setLevel(level)
        try:
            yield
        finally:
            self._logger.setLevel(orig_level)

    def is_debug_enabled(self):
        return self._logger.getEffectiveLevel() <= logging.DEBUG

    def info(self, *args, **kwargs):
        self._logger.info(*args, **kwargs)

    def warn(self, *args, **kwargs):
        self._logger.warn(*args, **kwargs)

    def debug(self, *args, **kwargs):
        self._logger.debug(*args, **kwargs)

    def error(self, *args, **kwargs):
        self._logger.error(*args, **kwargs)

    def add(self, msg):
        _write_with_fallback(msg, sys.stdout.write, sys.stdout)
        sys.stdout.flush()

log = Log()
