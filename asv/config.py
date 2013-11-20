# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

from . import util


class Config(object):
    """
    Manages the configuration for a benchmark project.
    """

    def __init__(self):
        self.project = "project"
        self.project_url = "#"
        self.repo = None
        self.pythons = ["{0.major}.{0.minor}".format(sys.version_info)]
        self.matrix = {}
        self.env_dir = "env"
        self.benchmark_dir = "benchmarks"
        self.results_dir = "results"
        self.html_dir = "html"
        self.show_commit_url = "#"
        self.hash_length = 8

    @staticmethod
    def from_file(path=None):
        """
        Load a configuration from a file.  If no file is provided,
        defaults to `asv.conf.json`.
        """
        if not path:
            path = "asv.conf.json"

        if not os.path.exists(path):
            raise RuntimeError("Config file {0} not found.".format(path))

        conf = Config()

        d = util.load_json(path)
        conf.__dict__.update(d)

        if not getattr(conf, "repo", None):
            raise ValueError(
                "No repo specified in {0} config file.".format(path))

        return conf
