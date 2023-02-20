# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os

import pytest

from asv.util import check_output, which, ProcessError

from . import tools
from .conftest import generate_basic_conf

WIN = (os.name == 'nt')

# Variables
try:
    defaultBranch = check_output([which('git'),
                                  'config', 'init.defaultBranch'],
                                 display_error=False).strip()
except ProcessError:
    defaultBranch = 'master'


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

    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir,
                                                            values=values,
                                                            dummy_packages=False)

    # Test find at least runs
    tools.run_asv_with_conf(conf, 'find',
                            f"{defaultBranch}~5..{defaultBranch}",
                            "params_examples.track_find_test",
                            _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', f'{defaultBranch}^'], cwd=conf.repo)

    assert f"Greatest regression found: {regression_hash[:8]}" in output


@pytest.mark.flaky(reruns=1, reruns_delay=5)  # depends on a timeout
def test_find_timeout(capfd, tmpdir):
    values = [
        (1, 0),
        (1, 0),
        (1, -1)
    ]

    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir,
                                                            values=values,
                                                            dummy_packages=False)

    # Test find at least runs
    tools.run_asv_with_conf(conf, 'find', "-e",
                            f"{defaultBranch}",
                            "params_examples.time_find_test_timeout",
                            _machine_file=machine_file)

    # Check it found the first commit after the initially tested one
    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', f'{defaultBranch}'], cwd=conf.repo)

    assert f"Greatest regression found: {regression_hash[:8]}" in output
    assert "asv: benchmark timed out (timeout 1.0s)" in output


def test_find_inverted(capfd, tmpdir):
    values = [
        (5, 6),
        (6, 6),
        (6, 6),
        (6, 1),
        (6, 1),
    ]

    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir,
                                                            values=values,
                                                            dummy_packages=False)
    tools.run_asv_with_conf(*[conf, 'find',
                              "-i", f"{defaultBranch}~4..{defaultBranch}",
                              "params_examples.track_find_test"],
                            _machine_file=machine_file)

    output, err = capfd.readouterr()

    regression_hash = check_output(
        [which('git'), 'rev-parse', f'{defaultBranch}^'], cwd=conf.repo)

    formatted = f"Greatest improvement found: {regression_hash[:8]}"
    assert formatted in output
