# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import pytest

from asv import config
from asv import environment
from asv import util


try:
    util.which('python2.7')
    HAS_PYTHON_27 = True
except RuntimeError:
    HAS_PYTHON_27 = False


try:
    util.which('python3.4')
    HAS_PYTHON_34 = True
except RuntimeError:
    HAS_PYTHON_34 = False


@pytest.mark.xfail(not HAS_PYTHON_27 or not HAS_PYTHON_34,
                   reason="Requires Python 2.7 and 3.4")
def test_matrix_environments(tmpdir):
    conf = config.Config()

    conf.env_dir = six.text_type(tmpdir.join("env"))

    conf.pythons = ["2.7", "3.4"]
    conf.matrix = {
        "six": ["1.4", None],
        "psutil": ["1.2", "2.1"]
    }
    environments = list(environment.get_environments(conf, None))

    assert len(environments) == 2 * 2 * 2

    # Only test the first two environments, since this is so time
    # consuming
    for env in environments[:2]:
        env.setup()
        env.install_requirements()

        output = env.run(
            ['-c', 'import six, sys; sys.stdout.write(six.__version__)'])
        if env._requirements['six'] is not None:
            assert output.startswith(six.text_type(env._requirements['six']))

        output = env.run(
            ['-c', 'import psutil, sys; sys.stdout.write(psutil.__version__)'])
        assert output.startswith(six.text_type(env._requirements['psutil']))


@pytest.mark.xfail(not HAS_PYTHON_27,
                   reason="Requires Python 2.7")
def test_large_environment_matrix(tmpdir):
    # As seen in issue #169, conda can't handle using really long
    # directory names in its environment.  This creates an environment
    # with many dependencies in order to ensure it still works.

    conf = config.Config()

    conf.env_dir = six.text_type(tmpdir.join("env"))
    conf.pythons = ["2.7"]
    for i in range(25):
        conf.matrix['foo{0}'.format(i)] = []

    environments = list(environment.get_environments(conf, None))

    for env in environments:
        # Since *actually* installing all the dependencies would make
        # this test run a long time, we only set up the environment,
        # but don't actually install dependencies into it.  This is
        # enough to trigger the bug in #169.
        env.setup()
