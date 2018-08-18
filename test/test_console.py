# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import io
import os
import sys
import locale
import itertools

from asv.console import _write_with_fallback, color_print, log


def test_write_with_fallback(tmpdir, capfd):
    tmpdir = six.text_type(tmpdir)

    def check_write(value, expected, stream_encoding, preferred_encoding):
        old_getpreferredencoding = locale.getpreferredencoding
        try:
            locale.getpreferredencoding = lambda: preferred_encoding

            # Check writing to io.StringIO
            stream = io.StringIO()
            _write_with_fallback(value, stream.write, stream)
            assert stream.getvalue() == value

            # Check writing to a text stream
            buf = io.BytesIO()
            stream = io.TextIOWrapper(buf, encoding=stream_encoding)
            _write_with_fallback(value, stream.write, stream)
            stream.flush()
            got = buf.getvalue()
            assert got == expected

            # Check writing to a byte stream (no stream encoding, so
            # it should write in locale encoding)
            if stream_encoding == preferred_encoding:
                buf = io.BytesIO()
                _write_with_fallback(value, buf.write, buf)
                got = buf.getvalue()
                assert got == expected

            # Check writing to a file
            fn = os.path.join(tmpdir, 'tmp.txt')
            with io.open(fn, 'w', encoding=stream_encoding) as stream:
                _write_with_fallback(value, stream.write, stream)
            with open(fn, 'rb') as stream:
                got = stream.read()
                assert got == expected

            # Check writing to Py2 files
            if not six.PY3:
                if stream_encoding == preferred_encoding:
                    # No stream encoding: write in locale encoding
                    for mode in ['w', 'wb']:
                        with open(fn, mode) as stream:
                            _write_with_fallback(value, stream.write, stream)
                        with open(fn, 'rb') as stream:
                            got = stream.read()
                            assert got == expected
        finally:
            locale.getpreferredencoding = old_getpreferredencoding

    # What is printed should follow the following rules:
    #
    # - Try printing in stream encoding.
    # - Try printing in locale preferred encoding.
    # - Otherwise, map characters produced by asv to ascii equivalents, and
    #   - Try to print in latin1
    #   - Try to print in ascii, replacing all non-ascii characters
    encodings = ['utf-8', 'latin1', 'ascii', 'euc-jp']
    strings = ["helloμ", "hello·", "hello難", "helloä", "hello±"]
    repmap = {"helloμ": "hellou", "hello·": "hello-", "hello±": "hello~"}

    for pref_enc, stream_enc, s in itertools.product(encodings, encodings, strings):
        expected = None
        for enc in [stream_enc, pref_enc]:
            try:
                expected = s.encode(enc)
                break
            except UnicodeError:
                pass
        else:
            s2 = repmap.get(s, s)
            try:
                expected = s2.encode('latin1')
            except UnicodeError:
                expected = s2.encode('ascii', 'replace')

        check_write(s, expected, stream_enc, pref_enc)

    # Should not bail out on bytes input
    _write_with_fallback("a".encode('ascii'), sys.stdout.write, sys.stdout)
    out, err = capfd.readouterr()
    assert out == "a"


def test_color_print_nofail(capfd):
    # Try out color print

    color_print("hello", "red")
    color_print("indeed難", "blue")
    color_print(b"really\xfe", "green", "not really")

    out, err = capfd.readouterr()
    assert 'hello' in out
    assert 'indeed' in out
    assert 'really' in out
    assert 'not really' in out


def test_log_indent(capsys):
    log.set_nitems(0)
    log.info("First\nSecond")

    out, err = capsys.readouterr()
    lines = out.lstrip().splitlines()
    assert lines[0].index('First') == lines[1].index('Second')

    log.set_nitems(1)
    log.info("First\nSecond")

    out, err = capsys.readouterr()
    lines = out.lstrip().splitlines()
    assert lines[0].index('First') == lines[1].index('Second')
