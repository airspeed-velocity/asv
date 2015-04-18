# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys
import time

from asv import util


def test_timeout():
    timeout_codes = []
    timeout_codes.append(r"""
import sys
import time

sys.stdout.write("Stdout before waiting\n")
sys.stderr.write("Stderr before waiting\n")
sys.stdout.flush()
sys.stderr.flush()
time.sleep(60)
sys.stdout.write("Stdout after waiting\n")
sys.stderr.write("Stderr after waiting\n")
    """)

    # Another example, where timeout is due to a hanging sub-subprocess
    if getattr(os, 'setpgid', None):
        # only on posix
        timeout_codes.append(r"""
import sys
import time
import subprocess

sys.stdout.write("Stdout before waiting\n")
sys.stderr.write("Stderr before waiting\n")
sys.stdout.flush()
sys.stderr.flush()
subprocess.call([sys.executable, "-c",
    "import sys, subprocess; subprocess.call([sys.executable, '-c', 'import time; time.sleep(60)'])"])
sys.stdout.write("Stdout after waiting\n")
sys.stderr.write("Stderr after waiting\n")
        """)

    for timeout_code in timeout_codes:
        t = time.time()
        try:
            util.check_output([
                sys.executable, "-c", timeout_code], timeout=1)
        except util.ProcessError as e:
            assert len(e.stdout.strip().split('\n')) == 1
            assert len(e.stderr.strip().split('\n')) == 1
            print(e.stdout)
            assert e.stdout.strip() == "Stdout before waiting"
            assert e.stderr.strip() == "Stderr before waiting"
            assert e.retcode == util.TIMEOUT_RETCODE
            assert "timed out" in str(e)
        else:
            assert False, "Expected timeout exception"
        # Make sure the timeout is triggered in a sufficiently short amount of time
        assert time.time() - t < 5.0


def test_exception():
    code = r"""
import sys
sys.stdout.write("Stdout before error\n")
sys.stderr.write("Stderr before error\n")
sys.exit(1)
"""
    try:
        util.check_output([
            sys.executable, "-c", code])
    except util.ProcessError as e:
        assert len(e.stdout.strip().split('\n')) == 1
        assert len(e.stderr.strip().split('\n')) == 1
        assert e.stdout.strip() == "Stdout before error"
        assert e.stderr.strip() == "Stderr before error"
        assert e.retcode == 1
        assert "returned non-zero exit status 1" in str(e)
    else:
        assert False, "Expected exception"


# This *does* seem to work, only seems untestable somehow...
# def test_dots(capsys):
#     code = r"""
# import sys
# import time
# for i in range(100):
#     sys.stdout.write("Line {0}\n".format(i))
#     sys.stdout.flush()
#     time.sleep(0.001)
# """
#     util.check_output([sys.executable, "-c", code])

#     out, err = capsys.readouterr()

#     assert out == '.' * 100
