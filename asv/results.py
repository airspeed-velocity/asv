# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os

from . import environment


class Results(object):
    def __init__(self, params, python, configuration, githash, date):
        self.params = params
        self.python = python
        self.configuration = configuration
        self.githash = githash
        self.date = date

        self.filename = "{0}-{1}.json".format(
            self.githash,
            environment.configuration_to_string(self.python, self.configuration))

    def add_times(self, times):
        self.results = times

    def save(self, result_dir):
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        with io.open(os.path.join(result_dir, self.filename), 'wb') as fd:
            json.dump({
                'results': self.results,
                'params': self.params,
                'githash': self.githash,
                'date': self.date
                }, fd)

    @classmethod
    def load(cls, path):
        with io.open(path, 'rb') as fd:
            d = json.load(fd)

        obj = cls(d['params'], d['params']['python'], {}, d['githash'], d['date'])
        obj.add_times(d['results'])
        return obj
