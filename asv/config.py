# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import sys


class Config(object):
    def __init__(self):
        self.package = "package"
        self.pythons = ["{0.major}.{0.minor}".format(sys.version_info)]
        self.matrix = {}
        self.repo = None
        self.benchmark_dir = "benchmarks"
        self.results_dir = "results"
        self.publish_dir = "html"
        self.project_url = "#"
        self.show_commit_url = "#"

    @staticmethod
    def from_file(path):
        if not path:
            path = "asv.conf.json"

        if not os.path.exists(path):
            raise RuntimeError("Config file {0} not found.".format(path))

        conf = Config()
        with io.open(path, "rb") as fd:
            conf.__dict__.update(json.load(fd))

        if not hasattr(conf, "repo"):
            raise ValueError(
                "No repo specified in {0} config file.".format(path))

        return conf
