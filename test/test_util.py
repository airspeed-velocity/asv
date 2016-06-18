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
import traceback
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

    os.makedirs(dirname)
    shutil.copyfile(sys.executable, os.path.join(dirname, fn))

    old_path = os.environ.get('PATH', '')
    try:
        if WIN:
            os.environ['PATH'] = old_path + os.pathsep + '"' + dirname + '"'
            util.which('asv_test_exe_1234')
            util.which('asv_test_exe_1234.exe')

        os.environ['PATH'] = old_path + os.pathsep + dirname
        util.which('asv_test_exe_1234.exe')
        if WIN:
            util.which('asv_test_exe_1234')
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
