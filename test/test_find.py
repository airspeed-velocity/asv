# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

import pytest

from asv.util import check_output, which

from . import tools
from .test_workflow import generate_basic_conf


WIN = (os.name == 'nt')


def test_find(capfd, tmpdir):
    values = [
        (None, None),
        (1, 1),
        (3, 1),
        (None, 1),
        (6, None),
        (5, 1),
        (6, 1),
        (6, 1),
        (6, 6),
        (6, 6),
    ]

    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir, values=values, dummy_packages=False)

    # Test find at least runs
    tools.run_asv_with_conf(conf, 'find', "master~5..master", "params_examples.track_find_test",
                            _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', 'master^'], cwd=conf.repo)

    assert "Greatest regression found: {0}".format(regression_hash[:8]) in output


@pytest.mark.flaky(reruns=1, reruns_delay=5)  # depends on a timeout
def test_find_timeout(capfd, tmpdir):
    values = [
        (1, 0),
        (1, 0),
        (1, -1)
    ]

    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir, values=values, dummy_packages=False)

    # Test find at least runs
    tools.run_asv_with_conf(conf, 'find', "-e", "master", "params_examples.time_find_test_timeout",
                            _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', 'master'], cwd=conf.repo)

    assert "Greatest regression found: {0}".format(regression_hash[:8]) in output
    assert "asv: benchmark timed out (timeout 1.0s)" in output
