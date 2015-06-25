# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import sys

from . import util

# TODO: Some verification of the config values

class Config(object):
    """
    Manages the configuration for a benchmark project.
    """
    api_version = 1

    def __init__(self):
        self.project = "project"
        self.project_url = "#"
        self.repo = None
        self.branches = [None]
        self.pythons = ["{0[0]}.{0[1]}".format(sys.version_info)]
        self.matrix = {}
        self.env_dir = "env"
        self.benchmark_dir = "benchmarks"
        self.results_dir = "results"
        self.html_dir = "html"
        self.show_commit_url = "#"
        self.hash_length = 8
        self.environment_type = None
        self.dvcs = None
        self.plugins = []

    @classmethod
    def load(cls, path=None):
        """
        Load a configuration from a file.  If no file is provided,
        defaults to `asv.conf.json`.
        """
        if not path:
            path = "asv.conf.json"

        if not os.path.isfile(path):
            raise util.UserError("Config file {0} not found.".format(path))

        d = util.load_json(path, cls.api_version)
        try:
            return cls.from_json(d)
        except ValueError:
            raise util.UserError(
                "No repo specified in {0} config file.".format(path))

    @classmethod
    def from_json(cls, d):
        conf = cls()
        conf.__dict__.update(d)

        if not getattr(conf, "repo", None):
            raise util.UserError(
                "No repo specified in config file.")

        if not getattr(conf, "branches", [None]):
            # If 'branches' attribute is present, at least some must
            # be listed.
            raise util.UserError(
                "No branches specified in config file.")

        return conf

    @classmethod
    def update(cls, path=None):
        if not path:
            path = "asv.conf.json"

        if not os.path.isfile(path):
            raise util.UserError("Config file {0} not found.".format(path))

        util.update_json(cls, path, cls.api_version)
