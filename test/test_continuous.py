# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
import re

from asv.results import iter_results_for_machine

from . import tools
from .tools import dummy_packages, get_default_environment_type
from .test_workflow import basic_conf


def test_continuous(capfd, basic_conf):
    tmpdir, local, conf, machine_file = basic_conf

    python = "{0[0]}.{0[1]}".format(sys.version_info)
    env_type = get_default_environment_type(conf, python)
    env_spec = ("-E", env_type + ":" + python)

    # Check that asv continuous runs
    tools.run_asv_with_conf(conf, 'continuous', "master^", '--show-stderr',
                            '--bench=params_examples.track_find_test',
                            '--bench=params_examples.track_param',
                            '--bench=time_examples.TimeSuite.time_example_benchmark_1',
                            '--attribute=repeat=1', '--attribute=number=1',
                            '--attribute=warmup_time=0',
                            *env_spec, _machine_file=machine_file)

    text, err = capfd.readouterr()
    assert "SOME BENCHMARKS HAVE CHANGED SIGNIFICANTLY" in text
    assert "PERFORMANCE INCREASED" in text or "PERFORMANCE DECREASED" in text
    assert "+               1                6     6.00  params_examples.track_find_test(2)" in text
    assert "params_examples.ClassOne" in text

    # Check rounds were interleaved (timing benchmark was run twice)
    assert re.search(r"For.*commit [a-f0-9]+ (<[a-z0-9~^]+> )?\(round 1/2\)", text, re.M), text

    result_found = False
    for results in iter_results_for_machine(conf.results_dir, "orangutan"):
        result_found = True
        stats = results.get_result_stats('time_examples.TimeSuite.time_example_benchmark_1', [])
        assert stats[0]['repeat'] == 2
    assert result_found
