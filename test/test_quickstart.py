# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from os.path import isfile, join

import six

from asv.commands.quickstart import Quickstart


def test_quickstart(tmpdir):
    tmpdir = six.text_type(tmpdir)

    Quickstart.run(tmpdir)

    assert isfile(join(tmpdir, 'asv.conf.json'))
    assert isfile(join(tmpdir, 'benchmarks', 'benchmarks.py'))
