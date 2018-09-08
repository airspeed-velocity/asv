# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import locale
import os
import sys
import shutil
import pickle
import multiprocessing
import threading
import traceback
import time
import datetime
import six
import pytest

from asv import console
from asv import util


WIN = (os.name == 'nt')


def _multiprocessing_raise_processerror(arg):
    try:
        raise util.ProcessError(["a"], 1, "aa", "bb")
    except BaseException as exc:
        # If the following is just 'raise', multiprocessing will hang
        # on Python 2.7.8 due to https://bugs.python.org/issue9400
        raise util.ParallelFailure(str(exc), exc.__class__, traceback.format_exc())


def _multiprocessing_raise_usererror(arg):
    try:
        raise util.UserError("hello")
    except BaseException as exc:
        raise util.ParallelFailure(str(exc), exc.__class__, traceback.format_exc())


@pytest.mark.timeout(30)
def test_parallelfailure():
    # Check the workaround for https://bugs.python.org/issue9400 works

    if WIN and os.path.basename(sys.argv[0]).lower().startswith('py.test'):
        # Multiprocessing in spawn mode can result to problems with py.test
        pytest.skip("Multiprocessing spawn mode on Windows not safe to run "
                    "from py.test runner.")

    # The exception class must be pickleable
    exc = util.ParallelFailure("test", Exception, "something")
    exc2 = pickle.loads(pickle.dumps(exc))
    assert exc.message == exc2.message
    assert exc.exc_cls == exc2.exc_cls
    assert exc.traceback_str == exc2.traceback_str
    assert str(exc) == "Exception: test\n    something"

    # Check multiprocessing does not hang (it would hang on Python
    # 2.7.8 if the 'raise utill.ParallelFailure ...' above is changed
    # to just 'raise')
    pool = multiprocessing.Pool(4)
    try:
        pool.map(_multiprocessing_raise_processerror, range(10))
    except util.ParallelFailure as exc:
        pass
    finally:
        pool.close()

    # Check reraising UserError
    pool = multiprocessing.Pool(4)
    try:
        try:
            pool.map(_multiprocessing_raise_usererror, range(10))
        except util.ParallelFailure as exc:
            exc.reraise()
        finally:
            pool.close()
        assert False
    except util.UserError as exc:
        # OK
        pass


def test_write_unicode_to_ascii():
    def get_fake_encoding():
        return 'ascii'

    original_getpreferredencoding = locale.getpreferredencoding
    locale.getpreferredencoding = get_fake_encoding

    try:
        buff = io.BytesIO()
        console.color_print("μs", file=buff)
        assert buff.getvalue() == b'us\n'
    finally:
        locale.getpreferredencoding = original_getpreferredencoding


def test_which_path(tmpdir):
    dirname = os.path.abspath(os.path.join(str(tmpdir), 'name with spaces'))
    fn = 'asv_test_exe_1234.exe'
    fn2 = 'asv_test_exe_4321.bat'

    os.makedirs(dirname)
    shutil.copyfile(sys.executable, os.path.join(dirname, fn))
    shutil.copyfile(sys.executable, os.path.join(dirname, fn2))

    old_path = os.environ.get('PATH', '')
    try:
        if WIN:
            os.environ['PATH'] = old_path + os.pathsep + '"' + dirname + '"'
            util.which('asv_test_exe_1234')
            util.which('asv_test_exe_1234.exe')
            util.which('asv_test_exe_4321')
            util.which('asv_test_exe_4321.bat')

        os.environ['PATH'] = old_path + os.pathsep + dirname
        util.which('asv_test_exe_1234.exe')
        util.which('asv_test_exe_4321.bat')
        if WIN:
            util.which('asv_test_exe_1234')
            util.which('asv_test_exe_4321')

        # Check the paths= argument
        util.which('asv_test_exe_1234.exe', paths=[dirname])
        util.which('asv_test_exe_4321.bat', paths=[dirname])

        # Check non-existent files
        with pytest.raises(IOError):
            util.which('nonexistent.exe', paths=[dirname])
    finally:
        os.environ['PATH'] = old_path


def test_write_load_json(tmpdir):
    data = {
        'a': 1,
        'b': 2,
        'c': 3
    }
    orig_data = dict(data)

    filename = os.path.join(six.text_type(tmpdir), 'test.json')

    util.write_json(filename, data)
    data2 = util.load_json(filename)
    assert data == orig_data
    assert data2 == orig_data

    util.write_json(filename, data, 3)
    data2 = util.load_json(filename, 3)
    assert data == orig_data
    assert data2 == orig_data

    # Wrong API version must fail to load
    with pytest.raises(util.UserError):
        util.load_json(filename, 2)
    with pytest.raises(util.UserError):
        util.load_json(filename, 4)
    util.write_json(filename, data)
    with pytest.raises(util.UserError):
        util.load_json(filename, 3)


def test_human_float():
    items = [
        # (expected, value, significant, truncate_small, significant_zeros, reference_value)

        # significant
        ("1", 1.2345, 1),
        ("1.2", 1.2345, 2),
        ("1.23", 1.2345, 3),
        ("100", 123.45, 1),
        ("120", 123.45, 2),
        ("123", 123.45, 3),
        ("123.5", 123.45, 4),
        ("0.001", 0.0012346, 1),
        ("0.001235", 0.0012346, 4),

        # significant zeros
        ("0.001", 0.001, 1, None, True),
        ("0.0010", 0.001, 2, None, True),
        ("0.00100", 0.001, 3, None, True),
        ("1", 1, 1, None, True),
        ("1.0", 1, 2, None, True),
        ("1.00", 1, 3, None, True),

        # truncate small
        ("0", 0.001, 2, 0),
        ("0", 0.001, 2, 1),
        ("0.001", 0.001, 2, 2),

        # non-finite
        ("inf", float('inf'), 1),
        ("-inf", -float('inf'), 1),
        ("nan", float('nan'), 1),

        # negative
        ("-1", -1.2345, 1),
        ("-0.00100", -0.001, 3, None, True),
        ("-0", -0.001, 2, 1),
        ("-0.001", -0.001, 2, 2),
    ]

    for item in items:
        expected = item[0]
        got = util.human_float(*item[1:])
        assert got == expected, item


def test_human_time():
    items = [
        # (expected, value, err)

        # scales
        ("1.00ns", 1e-9),
        ("1.10μs", 1.1e-6),
        ("1.12ms", 1.12e-3),
        ("1.12s", 1.123),
        ("1.13s", 1.126),
        ("1.00m", 60),
        ("2.00h", 3600*2),

        # err
        ("1.00±1ns", 1e-9, 1e-9),
        ("1.00±0.1ns", 1e-9, 0.1e-9),
        ("1.00±0.01ns", 1e-9, 0.01e-9),
        ("1.00±0.01ns", 1e-9, 0.006e-9),
        ("1.00±0ns", 1e-9, 0.001e-9),
    ]

    for item in items:
        expected = item[0]
        got = util.human_time(*item[1:])
        assert got == expected, item
        got = util.human_value(item[1], 'seconds', *item[2:])
        assert got == expected, item


def test_human_file_size():
    items = [
        # (expected, value, err)

        # scales
        ("1", 1),
        ("999", 999),
        ("1k", 1000),
        ("1.1M", 1.1e6),
        ("1.12G", 1.12e9),
        ("1.12T", 1.123e12),

        # err
        ("1±2", 1, 2),
        ("1±0.1k", 1e3, 123),
        ("12.3±4M", 12.34e6, 4321e3),
    ]

    for item in items:
        expected = item[0]
        got = util.human_file_size(*item[1:])
        assert got == expected, item
        got = util.human_value(item[1], 'bytes', *item[2:])
        assert got == expected, item


def test_is_main_thread():
    if sys.version_info[0] >= 3:
        # NB: the test itself doesn't necessarily run in main thread...
        is_main = (threading.current_thread() == threading.main_thread())
        assert util.is_main_thread() == is_main

    results = []

    def worker():
        results.append(util.is_main_thread())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert results == [False]


def test_json_non_ascii(tmpdir):
    non_ascii_data = [{'😼': '難', 'ä': 3}]

    fn = os.path.join(str(tmpdir), "nonascii.json")
    util.write_json(fn, non_ascii_data)
    data = util.load_json(fn)

    assert data == non_ascii_data


def test_interpolate_command():
    good_items = [
        ('python {inputs}', dict(inputs='9'),
         ['python', '9'], {}, {0}),

        ('python "{inputs}"', dict(inputs='9'),
         ['python', '9'], {}, {0}),

        ('python {inputs}', dict(inputs=''),
         ['python', ''], {}, {0}),

        ('HELLO="asd" python "{inputs}"', dict(inputs='9'),
         ['python', '9'], {'HELLO': 'asd'}, {0}),

        ('HELLO="asd" return-code=any python "{inputs}"', dict(inputs='9'),
         ['python', '9'], {'HELLO': 'asd'}, None),

        ('HELLO="asd" return-code=255 python "{inputs}"', dict(inputs='9'),
         ['python', '9'], {'HELLO': 'asd'}, {255}),

        ('HELLO="asd" return-code=255 python "{inputs}"', dict(inputs='9'),
         ['python', '9'], {'HELLO': 'asd'}, {255}),
    ]

    bad_items = [
        ('python {foo}', {}),
        ('HELLO={foo} python', {}),
        ('return-code=none python', {}),
        ('return-code= python', {}),
        ('return-code=, python', {}),
        ('return-code=1,,2 python', {}),
        ('return-code=1 return-code=2 python', {}),
    ]

    for value, variables, e_parts, e_env, e_codes in good_items:
        parts, env, codes = util.interpolate_command(value, variables)
        assert parts == e_parts
        assert env == e_env
        assert codes == e_codes

    for value, variables in bad_items:
        with pytest.raises(util.UserError):
            util.interpolate_command(value, variables)


def test_datetime_to_js_timestamp():
    tss = [0, 0.5, -0.5, 12345.6789, -12345.6789,
           1535910708.7767508]
    for ts in tss:
        t = datetime.datetime.utcfromtimestamp(ts)
        ts2 = util.datetime_to_js_timestamp(t)
        assert abs(ts * 1000 - ts2) <= 0.5

    # Check sub-second precision
    ms = 50
    ts = datetime.datetime(1970, 1, 1, 0, 0, 0, 1000*ms)
    assert util.datetime_to_js_timestamp(ts) == ms

    # Check rounding
    ts = datetime.datetime(1970, 1, 1, 0, 0, 0, 500)
    assert util.datetime_to_js_timestamp(ts) == 1
    ts = datetime.datetime(1970, 1, 1, 0, 0, 0, 499)
    assert util.datetime_to_js_timestamp(ts) == 0


def test_datetime_to_timestamp():
    tss = [0, 0.5, -0.5, 12345.6789, -12345.6789,
           1535910708.7767508]
    for ts in tss:
        t = datetime.datetime.utcfromtimestamp(ts)
        ts2 = util.datetime_to_timestamp(t)
        assert abs(ts - ts2) <= 0.5

    # Check rounding
    ts = datetime.datetime(1970, 1, 1, 0, 0, 0, 500000)
    assert util.datetime_to_timestamp(ts) == 1
    ts = datetime.datetime(1970, 1, 1, 0, 0, 0, 500000 - 1)
    assert util.datetime_to_timestamp(ts) == 0
