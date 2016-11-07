# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import inspect  # Checked below.
import sys


class ImpSuite(object):
    def imp_fresh(self):
        # The test interpreter should not be polluted with anything.
        import sys
        assert 'asv' not in sys.modules
        assert 'inspect' not in sys.modules

    def imp_docstring(self):
        """
        Docstrings may be used to comment benchmarks.
        """
        pass

    def imp_timeout(self):
        # Inside the grandchild.
        while True:
            pass
    imp_timeout.timeout = .1

    def imp_count(self):
        # Using number other than one or a fixed repeat should work.
        import sys
        sys.stderr.write('0')
    imp_count.number = 3
    imp_count.repeat = 7
