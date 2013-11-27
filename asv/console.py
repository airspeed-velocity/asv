# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
A set of utilities for writing output to the console.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import codecs
import contextlib
import locale
import sys

import six


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

    enc = locale.getpreferredencoding()
    try:
        try:
            return s.decode(enc)
        except LookupError:
            enc = 'utf-8'
        return s.decode(enc)
    except UnicodeDecodeError:
        return s.decode('latin-1')


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

    if sys.platform == 'win32':
        return text

    color_code = color_mapping.get(color, '0;39')
    return '\033[{0}m{1}\033[0m'.format(color_code, text)


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
    write(s)
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

            # Some file objects support writing unicode sensibly on some Python
            # versions; if this fails try creating a writer using the locale's
            # preferred encoding. If that fails too give up.
            if not six.PY3 and isinstance(msg, bytes):
                msg = _decode_preferred_encoding(msg)

            write = _write_with_fallback(msg, write, file)

        write(end)
    else:
        for i in xrange(0, len(args), 2):
            msg = args[i]
            if not six.PY3 and isinstance(msg, bytes):
                # Support decoding bytes to unicode on Python 2; use the
                # preferred encoding for the locale (which is *sometimes*
                # sensible)
                msg = _decode_preferred_encoding(msg)
            write(msg)
        write(end)


def get_answer_default(prompt, default):
    print("{0} [{1}]: ".format(prompt, default), end='')
    x = raw_input()
    if x.strip() == '':
        return default
    return x


class _Console(object):
    def __init__(self, stream=None):
        if stream is None:
            stream = sys.stdout
        self._stream = stream
        self._indent = 0
        self._needs_newline = False
        self._n_items = 0
        self._step = 0

    def _newline(self):
        if self._needs_newline:
            self._stream.write("\n")

    @contextlib.contextmanager
    def indent(self):
        """
        A context manager to increase the indentation level.
        """
        self._indent += 1
        yield
        self._indent -= 1

    def dot(self):
        self._stream.write('.')
        self._stream.flush()
        self._needs_newline = True

    def message(self, message, color='default'):
        """
        Write a message to the console.
        """
        self._newline()
        self._stream.write(' ' * self._indent)
        color_print(message, color, file=self._stream)
        self._stream.flush()
        self._needs_newline = True

    def add(self, message, color='default'):
        """
        Add content to the end of the message.
        """
        color_print(message, color, file=self._stream)
        self._stream.flush()

    @contextlib.contextmanager
    def group(self, message, color='default'):
        """
        Context manager for a new console grouping -- messages within
        the context will be indented.
        """
        self._newline()
        self._stream.write(' ' * self._indent)
        color_print(message, color, file=self._stream)
        self._stream.flush()
        self._needs_newline = True
        with self.indent():
            yield

    def set_nitems(self, n):
        """
        Set the number of items in a lengthy process.  Each of these
        steps should be incremented through using `step`.
        """
        self._n_items = n
        self._step = 0

    def step(self, message, color='default'):
        """
        Write that a step has been completed.  A percentage is
        displayed along with it.
        """
        self._newline()
        self._stream.write(' ' * self._indent)
        self._step += 1
        self._stream.write("[{0:.02f}%] ".format(
            (float(self._step) / self._n_items) * 100.0))
        color_print(message, color, file=self._stream)
        self._stream.flush()
        self._needs_newline = True

    def fake_step(self, n):
        """
        Increase the step count without displaying a message.
        """
        self._step += n

    def error(self, message, content=''):
        """
        Display an error to the console.
        """
        self._newline()
        color_print("ERROR: ", "red", file=self._stream)
        self._stream.write(message)
        self._stream.write("\n")
        self._stream.write(content)
        self._needs_newline = False

    def warning(self, message, content=''):
        """
        Display a warning to the console.
        """
        self._newline()
        color_print("WARNING: ", "yellow", file=self._stream)
        self._stream.write(message)
        self._stream.write("\n")
        self._stream.write(content)
        self._needs_newline = False

console = _Console()
