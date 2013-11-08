# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from . import environment
from . import util


class Results(object):
    def __init__(self, params, python, configuration, githash, date):
        self.params = params
        self.python = python
        self.githash = githash
        self.date = date

        self.filename = os.path.join(
            params['machine'],
            "{0}-{1}.json".format(
                self.githash[:8],
                environment.configuration_to_string(
                    self.python, configuration)))

    def add_times(self, times):
        self.results = times

    def save(self, result_dir):
        path = os.path.join(result_dir, self.filename)

        util.write_json(path, {
            'results': self.results,
            'params': self.params,
            'githash': self.githash,
            'date': self.date,
            'python': self.python
        })

    @classmethod
    def load(cls, path):
        d = util.load_json(path)

        obj = cls(
            d['params'],
            d['python'],
            {},
            d['githash'],
            d['date'])
        obj.add_times(d['results'])
        return obj
