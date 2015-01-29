# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil

import six

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..graph import Graph
from ..machine import iter_machine_files
from ..repo import get_repo
from ..results import iter_results
from .. import util


class Publish(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "publish", help="Collate results into a website",
            description=
            """
            Collate all results into a website.  This website will be
            written to the ``html_dir`` given in the ``asv.conf.json``
            file, and may be served using any static web server.""")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf)

    @classmethod
    def run(cls, conf):
        params = {}
        graphs = {}
        date_to_hash = {}
        machines = {}
        benchmark_names = set()

        log.set_nitems(5)

        if os.path.exists(conf.html_dir):
            shutil.rmtree(conf.html_dir)

        benchmarks = Benchmarks.load(conf)

        template_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'www')
        shutil.copytree(template_dir, conf.html_dir)

        log.step()
        log.info("Loading machine info")
        with log.indent():
            for path in iter_machine_files(conf.results_dir):
                d = util.load_json(path)
                machines[d['machine']] = d

        log.step()
        log.info("Loading results")
        with log.indent():
            for results in iter_results(conf.results_dir):
                log.dot()
                date_to_hash[results.date] = results.commit_hash[
                    :conf.hash_length]

                for key, val in six.iteritems(results.params):
                    params.setdefault(key, set())
                    params[key].add(val)

                for key, val in six.iteritems(results.results):
                    # Drop points in parameterized tests computed for
                    # parameter sets differing from the current set
                    b = benchmarks.get(key)
                    if not b and isinstance(val, dict):
                        result = None
                    elif b and b['params']:
                        if val and val['params'] == b['params']:
                            result = val['result']
                        else:
                            result = None
                    else:
                        result = val

                    benchmark_names.add(key)
                    graph = Graph(key, results.params, params)
                    if graph.path in graphs:
                        graph = graphs[graph.path]
                    else:
                        graphs[graph.path] = graph
                    graph.add_data_point(results.date, result)

                    graph = Graph(key, {'summary': None}, {}, summary=True)
                    if graph.path in graphs:
                        graph = graphs[graph.path]
                    else:
                        graphs[graph.path] = graph
                    graph.add_data_point(results.date, result)

        log.step()
        log.info("Generating graphs")
        with log.indent():
            for graph in six.itervalues(graphs):
                log.dot()
                graph.save(conf.html_dir)

        log.step()
        log.info("Getting tags")
        with log.indent():
            repo = get_repo(conf)
            repo.pull()
            tags = {}
            for tag in repo.get_tags():
                log.dot()
                tags[tag] = repo.get_date_from_tag(tag)

        log.step()
        log.info("Writing index")
        benchmark_map = dict(benchmarks)
        for key, val in six.iteritems(params):
            val = list(val)
            val.sort(key=lambda x: x or '')
            params[key] = val
        util.write_json(os.path.join(conf.html_dir, "index.json"), {
            'project': conf.project,
            'project_url': conf.project_url,
            'show_commit_url': conf.show_commit_url,
            'date_to_hash': date_to_hash,
            'params': params,
            'benchmarks': benchmark_map,
            'machines': machines,
            'tags': tags
        })
