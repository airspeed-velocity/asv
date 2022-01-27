# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
A set of utilities for writing output to the console.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import contextlib
import locale
import logging
import os
import sys
import textwrap
import time

import six
from six.moves import xrange, input

from . import util


WIN = (os.name == "nt")


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


# This is a table of Unicode characters that we want to have
# reasonable representations in ascii so they aren't just replaced
# with '?'.  A complete solution to this problem would involve a
# third-party library such as "unidecode", but this handles the common
# cases of stuff coming from asv.
#
# You can find the characters that need an entry using:
#    grep -P  -n '[^\x00-\x7F]' -r *
# in the `asv` source directory.

_unicode_translations = {
    ord('μ'): 'u',
    ord('·'): '-',
    ord('±'): '~'
}


def _write_with_fallback(s, fileobj):
    """
    Write the supplied string to the given stream, but switch to
    the locale's preferred encoding in case of a UnicodeEncodeError.
    Failing that, replace characters.
    *fileobj* must be text stream on Py3, on Py2 a `file` byte stream.
    *s* must be unicode.
    """
    if not isinstance(s, six.text_type):
        raise ValueError("Input string is not a Unicode string")

    if six.PY3:
        try:
            fileobj.write(s)
            return
        except UnicodeError:
            pass

        # Fall back to writing bytes
        enc = locale.getpreferredencoding()
        try:
            b = s.encode(enc)
        except UnicodeError:
            s = s.translate(_unicode_translations)
            b = s.encode(enc, errors='replace')

        fileobj.flush()
        fileobj.buffer.write(b)
    else:
        enc = locale.getpreferredencoding()
        try:
            b = s.encode(enc)
        except UnicodeError:
            unichr = _unicode_translations.iteritems()
            for key, val in unichr:
                s = s.replace(unichr(key), val)
            b = s.encode(enc, errors='replace')

        fileobj.write(b)


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
    end = kwargs.get('end', '\n')

    if isatty(file) and not WIN:
        for i in xrange(0, len(args), 2):
            msg = args[i]
            if i + 1 == len(args):
                color = ''
            else:
                color = args[i + 1]

            if color:
                msg = _color_text(msg, color)
            _write_with_fallback(msg, file)

        _write_with_fallback(end, file)
    else:
        for i in xrange(0, len(args), 2):
            msg = args[i]
            _write_with_fallback(msg, file)
        _write_with_fallback(end, file)


def get_answer_default(prompt, default, use_defaults=False):
    color_print("{0} [{1}]: ".format(prompt, default), end='')

    if use_defaults:
        return default

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
        self._last_dot = time.time()

    def _stream_formatter(self, record):
        '''
        The formatter for standard output
        '''
        if self._needs_newline:
            color_print('')
        parts = record.msg.split('\n', 1)
        first_line = parts[0]
        if len(parts) == 1:
            rest = None
        else:
            rest = parts[1]

        indent = self._indent + 1
        continued = getattr(record, 'continued', False)

        if self._total:
            progress_msg = '[{0:6.02f}%] '.format(
                (float(self._count) / self._total) * 100.0)
            if not continued:
                color_print(progress_msg, end='')
            indent += len(progress_msg)

        if not continued:
            color_print('·' * self._indent, end='')
            color_print(' ', end='')
        else:
            color_print(' ' * indent, end='')

        if hasattr(record, 'color'):
            color = record.color
        elif record.levelno < logging.DEBUG:
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

        spaces = ' ' * indent
        color_print(first_line, color, end='')
        if rest is not None:
            color_print('')
            detail = textwrap.dedent(rest)
            for line in detail.split('\n'):
                color_print(spaces, end='')
                color_print(line)

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
            if time.time() > self._last_dot + 1.0:
                color_print('.', 'darkgrey', end='')
                sys.stdout.flush()
                self._last_dot = time.time()

    def set_nitems(self, n):
        """
        Set the number of remaining items to process.  Each of these
        steps should be incremented through using `step`.

        Can be called multiple times. The progress percentage is ensured
        to be non-decreasing, except if 100% was already reached in which
        case it is restarted from 0%.
        """
        try:
            # Ensure count/total is nondecreasing
            self._total = util.ceildiv(n * self._total, self._total - self._count)
            self._count = self._total - n
        except ZeroDivisionError:
            # Reset counting from start
            self._total = n
            self._count = 0

    def step(self):
        """
        Write that a step has been completed.  A percentage is
        displayed along with it.

        If we are stepping beyond the number of items, stop counting.
        """
        self._count = min(self._total, self._count + 1)

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
        if not self.is_debug_enabled():
            self._logger.setLevel(level)
        try:
            yield
        finally:
            self._logger.setLevel(orig_level)

    def is_debug_enabled(self):
        return self._logger.getEffectiveLevel() <= logging.DEBUG

    def _message(self, routine, message, reserve_space=False, color=None,
                 continued=False):
        kwargs = {}
        extra = {}
        if color is not None:
            extra['color'] = color
        if continued:
            extra['continued'] = True
        if extra:
            kwargs['extra'] = extra

        if reserve_space:
            max_width = max(16, util.get_terminal_width() - 33)
            message = truncate_left(message, max_width)
            self._prev_message = message

        routine(message, **kwargs)

    def info(self, *args, **kwargs):
        self._message(self._logger.info, *args, **kwargs)

    def warning(self, *args, **kwargs):
        self._message(self._logger.warning, *args, **kwargs)

    def debug(self, *args, **kwargs):
        self._message(self._logger.debug, *args, **kwargs)

    def error(self, *args, **kwargs):
        self._message(self._logger.error, *args, **kwargs)

    def add(self, msg):
        if self._needs_newline:
            _write_with_fallback(msg, sys.stdout)
            sys.stdout.flush()
        else:
            self.info(msg)

    def add_padded(self, msg):
        """
        Final part of two-part info message.
        Should be preceded by a call to info/warn/...(msg, reserve_space=True)
        """
        if self._prev_message is None:
            # No previous part: print as an info message
            self.info(msg)
            return

        padding_length = util.get_terminal_width() - len(self._prev_message) - 14 - 1 - len(msg)
        if WIN:
            padding_length -= 1
        padding = " "*padding_length

        self._prev_message = None
        self.add(" {0}{1}".format(padding, msg))

    def flush(self):
        """
        Flush any trailing newlines. Needs to be called before printing
        to stdout via other means, after using Log.
        """
        if self._needs_newline:
            color_print('')
            self._needs_newline = False
        sys.stdout.flush()


log = Log()
