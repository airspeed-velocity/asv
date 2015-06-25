# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import time
import pickle
import multiprocessing
import subprocess
import traceback

from asv import util


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
