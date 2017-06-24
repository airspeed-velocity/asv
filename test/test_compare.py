# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
from os.path import abspath, dirname, join
import sys

import six

from asv import config

from asv.commands.compare import Compare
from argparse import Namespace

from . import tools

RESULT_DIR = abspath(join(dirname(__file__), 'example_results'))
MACHINE_FILE = abspath(join(dirname(__file__), 'asv-machine.json'))

REFERENCE = """
All benchmarks:

       before           after         ratio
     [22b920c6]       [fcf8c079]
!             n/a           failed      n/a  params_examples.ParamSuite.track_value
           failed           failed      n/a  time_AAA_failure
              n/a              n/a      n/a  time_AAA_skip
          1.00±1s          3.00±1s    ~3.00  time_ci_big
+         1.00±0s          3.00±0s     3.00  time_ci_small
!           454μs           failed      n/a  time_coordinates.time_latitude
            1.00s            1.00s     1.00  time_other.time_parameterized(1)
            2.00s            4.00s     2.00  time_other.time_parameterized(2)
!           3.00s           failed      n/a  time_other.time_parameterized(3)
+          1.75ms            153ms    87.28  time_quantity.time_quantity_array_conversion
+           934μs            108ms   115.90  time_quantity.time_quantity_init_array
           83.6μs           55.4μs     0.66  time_quantity.time_quantity_init_scalar
            282μs            147μs     0.52  time_quantity.time_quantity_scalar_conversion
+          1.31ms           7.75ms     5.91  time_quantity.time_quantity_ufunc_sin
            5.73m            5.73m     1.00  time_units.mem_unit
+           125μs           3.81ms    30.42  time_units.time_simple_unit_parse
           1.64ms           1.53ms     0.93  time_units.time_unit_compose
+           372μs           11.5ms    30.81  time_units.time_unit_parse
-          69.1μs           18.3μs     0.27  time_units.time_unit_to
           11.9μs           13.1μs     1.10  time_units.time_very_simple_unit_parse
+           1.00s            3.00s     3.00  time_with_version_match
+           1.00s            3.00s     3.00  time_with_version_mismatch_bench
x           1.00s            3.00s     3.00  time_with_version_mismatch_other
"""

REFERENCE_SPLIT = """
Benchmarks that have improved:

       before           after         ratio
     [22b920c6]       [fcf8c079]
-          69.1μs           18.3μs     0.27  time_units.time_unit_to

Benchmarks that have stayed the same:

       before           after         ratio
     [22b920c6]       [fcf8c079]
              n/a              n/a      n/a  time_AAA_skip
          1.00±1s          3.00±1s    ~3.00  time_ci_big
            1.00s            1.00s     1.00  time_other.time_parameterized(1)
            2.00s            4.00s     2.00  time_other.time_parameterized(2)
           83.6μs           55.4μs     0.66  time_quantity.time_quantity_init_scalar
            282μs            147μs     0.52  time_quantity.time_quantity_scalar_conversion
            5.73m            5.73m     1.00  time_units.mem_unit
           1.64ms           1.53ms     0.93  time_units.time_unit_compose
           11.9μs           13.1μs     1.10  time_units.time_very_simple_unit_parse

Benchmarks that have got worse:

       before           after         ratio
     [22b920c6]       [fcf8c079]
!             n/a           failed      n/a  params_examples.ParamSuite.track_value
           failed           failed      n/a  time_AAA_failure
+         1.00±0s          3.00±0s     3.00  time_ci_small
!           454μs           failed      n/a  time_coordinates.time_latitude
!           3.00s           failed      n/a  time_other.time_parameterized(3)
+          1.75ms            153ms    87.28  time_quantity.time_quantity_array_conversion
+           934μs            108ms   115.90  time_quantity.time_quantity_init_array
+          1.31ms           7.75ms     5.91  time_quantity.time_quantity_ufunc_sin
+           125μs           3.81ms    30.42  time_units.time_simple_unit_parse
+           372μs           11.5ms    30.81  time_units.time_unit_parse
+           1.00s            3.00s     3.00  time_with_version_match
+           1.00s            3.00s     3.00  time_with_version_mismatch_bench

Benchmarks that are not comparable:

       before           after         ratio
     [22b920c6]       [fcf8c079]
x           1.00s            3.00s     3.00  time_with_version_mismatch_other
"""

REFERENCE_ONLY_CHANGED = """
       before           after         ratio
     [22b920c6]       [fcf8c079]
!             n/a           failed      n/a  params_examples.ParamSuite.track_value
!           454μs           failed      n/a  time_coordinates.time_latitude
!           3.00s           failed      n/a  time_other.time_parameterized(3)
+           934μs            108ms   115.90  time_quantity.time_quantity_init_array
+          1.75ms            153ms    87.28  time_quantity.time_quantity_array_conversion
+           372μs           11.5ms    30.81  time_units.time_unit_parse
+           125μs           3.81ms    30.42  time_units.time_simple_unit_parse
+          1.31ms           7.75ms     5.91  time_quantity.time_quantity_ufunc_sin
+         1.00±0s          3.00±0s     3.00  time_ci_small
+           1.00s            3.00s     3.00  time_with_version_match
+           1.00s            3.00s     3.00  time_with_version_mismatch_bench
-          69.1μs           18.3μs     0.27  time_units.time_unit_to
"""

def test_compare(capsys, tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'results_dir': RESULT_DIR,
         'repo': tools.generate_test_repo(tmpdir).path,
         'project': 'asv',
         'environment_type': "shouldn't matter what"})

    tools.run_asv_with_conf(conf, 'compare', '22b920c6', 'fcf8c079', '--machine=cheetah',
                            '--factor=2')

    text, err = capsys.readouterr()
    assert text.strip() == REFERENCE.strip()

    tools.run_asv_with_conf(conf, 'compare', '22b920c6', 'fcf8c079', '--machine=cheetah',
                            '--factor=2', '--split')

    text, err = capsys.readouterr()
    assert text.strip() == REFERENCE_SPLIT.strip()

    # Check print_table output as called from Continuous
    status = Compare.print_table(conf, '22b920c6', 'fcf8c079', factor=2, machine='cheetah',
                                 split=False, only_changed=True, sort_by_ratio=True)
    worsened, improved = status
    assert worsened
    assert improved
    text, err = capsys.readouterr()
    assert text.strip() == REFERENCE_ONLY_CHANGED.strip()
