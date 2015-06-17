# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function


class ClassLevelSetup:
    @classmethod
    def setupclass(cls):
        assert not hasattr(cls, 'big_list')
        cls.big_list = [0] * 500

    def track_example(self):
        return len(self.big_list)

    def track_example2(self):
        return len(self.big_list)
