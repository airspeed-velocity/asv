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

from . import tools

RESULT_DIR = abspath(join(dirname(__file__), 'example_results'))
MACHINE_FILE = abspath(join(dirname(__file__), 'asv-machine.json'))

REFERENCE = """
All benchmarks:

    before     after       ratio
  [22b920c6] [fcf8c079]
!  454.03μs     failed       n/a  time_coordinates.time_latitude
      1.00s      1.00s      1.00  time_other.time_parameterized(1)
      2.00s      4.00s      2.00  time_other.time_parameterized(2)
!     3.00s     failed       n/a  time_other.time_parameterized(3)
+    1.75ms   152.84ms     87.28  time_quantity.time_quantity_array_conversion
+  933.71μs   108.22ms    115.90  time_quantity.time_quantity_init_array
    83.65μs    55.38μs      0.66  time_quantity.time_quantity_init_scalar
   281.71μs   146.88μs      0.52  time_quantity.time_quantity_scalar_conversion
+    1.31ms     7.75ms      5.91  time_quantity.time_quantity_ufunc_sin
      5.73m      5.73m      1.00  time_units.mem_unit
+  125.11μs     3.81ms     30.42  time_units.time_simple_unit_parse
     1.64ms     1.53ms      0.93  time_units.time_unit_compose
+  372.11μs    11.47ms     30.81  time_units.time_unit_parse
    69.09μs    48.32μs      0.70  time_units.time_unit_to
    11.87μs    13.10μs      1.10  time_units.time_very_simple_unit_parse
"""


def test_compare(capsys, tmpdir):
    tmpdir = six.text_type(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'results_dir': RESULT_DIR,
         'repo': tools.generate_test_repo(tmpdir).path,
         'project': 'asv'})

    Compare.run(conf, '22b920c6', 'fcf8c079', machine='cheetah')

    text, err = capsys.readouterr()
    assert text.strip() == REFERENCE.strip()
