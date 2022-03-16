# Licensed under a 3-clause BSD style license - see LICENSE.rst

import glob
import os
import sys
import json
from os.path import join, isfile

import pytest

from asv import util

from . import tools


def test_run_publish(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf
    tmpdir = util.long_path(tmpdir)

    conf.matrix = {
        "req": dict(conf.matrix),
        "env": {"SOME_TEST_VAR": ["1"]},
    }

    # Tests a typical complete run/publish workflow
    ret = tools.run_asv_with_conf(conf, 'run', "master", '--steps=2',
                                  '--quick', '--show-stderr', '--profile',
                                  '-a', 'warmup_time=0',
                                  '--durations=5',
                                  _machine_file=machine_file)
    assert ret is None
    text, err = capfd.readouterr()

    assert len(os.listdir(join(tmpdir, 'results_workflow', 'orangutan'))) == 5
    assert len(os.listdir(join(tmpdir, 'results_workflow'))) == 2
    assert 'asv: benchmark timed out (timeout 0.1s)' in text
    assert 'total duration' in text

    tools.run_asv_with_conf(conf, 'publish')

    assert isfile(join(tmpdir, 'html', 'index.html'))
    assert isfile(join(tmpdir, 'html', 'index.json'))
    assert isfile(join(tmpdir, 'html', 'asv.js'))
    assert isfile(join(tmpdir, 'html', 'asv.css'))

    # Check parameterized test json data format
    filename = glob.glob(join(tmpdir, 'html', 'graphs', 'arch-x86_64',
                              'asv_dummy_test_package_1',
                              'asv_dummy_test_package_2-' + tools.DUMMY2_VERSIONS[1],
                              'branch-master',
                              'cpu-Blazingly fast',
                              'env-SOME_TEST_VAR-1',
                              'machine-orangutan',
                              'os-GNU_Linux', 'python-*', 'ram-128GB',
                              'params_examples.time_skip.json'))[0]
    with open(filename, 'r') as fp:
        data = json.load(fp)
        assert len(data) == 2
        assert isinstance(data[0][0], int)  # revision
        assert len(data[0][1]) == 3
        assert len(data[1][1]) == 3
        assert isinstance(data[0][1][0], float)
        assert isinstance(data[0][1][1], float)
        assert data[0][1][2] is None

    # Check that the skip options work
    capfd.readouterr()
    tools.run_asv_with_conf(conf, 'run', "master", '--steps=2',
                            '--quick', '--skip-existing-successful',
                            '--bench=time_secondary.track_value',
                            '--skip-existing-failed',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    tools.run_asv_with_conf(conf, 'run', "master", '--steps=2',
                            '--bench=time_secondary.track_value',
                            '--quick', '--skip-existing-commits',
                            _machine_file=join(tmpdir, 'asv-machine.json'))
    text, err = capfd.readouterr()
    assert 'Running benchmarks.' not in text

    # Check EXISTING and --environment work
    python = "{0[0]}.{0[1]}".format(sys.version_info)
    env_type = tools.get_default_environment_type(conf, python)
    env_spec = ("-E", env_type + ":" + python)
    tools.run_asv_with_conf(conf, 'run', "EXISTING", '--quick',
                            '--bench=time_secondary.track_value',
                            *env_spec,
                            _machine_file=machine_file)

    # Remove the benchmarks.json file and check publish fails

    os.remove(join(tmpdir, "results_workflow", "benchmarks.json"))

    with pytest.raises(util.UserError):
        tools.run_asv_with_conf(conf, 'publish')
