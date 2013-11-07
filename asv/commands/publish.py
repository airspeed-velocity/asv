# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import json
import os
import shutil

import six

from ..config import Config
from ..console import console
from ..line import Line
from ..results import Results


class Publish(object):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser("publish", help="Publish results")

        parser.set_defaults(func=cls.run)

    @classmethod
    def run(cls, args):
        conf = Config.from_file(args.config)

        params = {}
        lines = {}
        date_to_hash = {}
        test_names = set()

        if os.path.exists(conf.publish_dir):
            shutil.rmtree(conf.publish_dir)

        template_dir = os.path.join(
            os.path.dirname(__file__), '..', 'www')
        shutil.copytree(template_dir, conf.publish_dir)

        dir_contents = os.listdir(conf.results_dir)
        with console.group("Loading results", "green"):
            console.set_nitems(len(dir_contents))
            for filename in dir_contents:
                console.step(filename)
                path = os.path.join(conf.results_dir, filename)
                if not os.path.isfile(path):
                    continue

                results = Results.load(path)

                date_to_hash[results.date * 1000] = results.githash

                for key, val in six.iteritems(results.params):
                    params.setdefault(key, set())
                    params[key].add(val)

                for key, val in six.iteritems(results.results):
                    test_names.add(key)
                    line = Line(key, results.params)
                    if line.path in lines:
                        line = lines[line.path]
                    else:
                        lines[line.path] = line
                    line.add_data_point(results.date, val)

        with console.group("Generating graphs", "green"):
            console.set_nitems(len(lines))
            for line in six.itervalues(lines):
                console.step(line.test_name)
                line.save(conf.publish_dir)

        with console.group("Writing index", "green"):
            test_names = list(test_names)
            test_names.sort()
            for key, val in six.iteritems(params):
                val = list(val)
                val.sort()
                params[key] = val
            with io.open(
                    os.path.join(conf.publish_dir, "index.json"), "wb") as fd:
                json.dump({
                    'package': conf.package,
                    'project_url': conf.project_url,
                    'show_commit_url': conf.show_commit_url,
                    'date_to_hash': date_to_hash,
                    'params': params,
                    'test_names': test_names
                }, fd)
