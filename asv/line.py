# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

import six

from . import util


class Line(object):
    def __init__(self, test_name, params):
        self.test_name = test_name
        self.params = params
        self.data_points = {}

        # TODO: Make filename safe
        parts = []

        l = list(six.iteritems(self.params))
        l.sort()
        for key, val in l:
            if val is None:
                parts.append(key)
            else:
                parts.append('{0}-{1}'.format(key, val))
        parts.append(test_name)

        self.path = os.path.join(*parts)

    def add_data_point(self, date, runtime):
        self.data_points[date * 1000] = runtime

    def save(self, publish_dir):
        filename = os.path.join(publish_dir, self.path + ".json")

        val = list(six.iteritems(self.data_points))
        val.sort()

        util.write_json(filename, val)
