# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
import itertools

import six

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..graph import Graph, make_summary_graph
from ..machine import iter_machine_files
from ..repo import get_repo
from ..results import iter_results, compatible_results
from ..branch_cache import BranchCache
from ..publishing import OutputPublisher
from .. import environment
from .. import util

from . import common_args


def check_benchmark_params(name, benchmark):
    """
    Check benchmark params and param_keys items, so that the javascript can
    assume this data is valid. It is checked in benchmark.py already when it
    is generated, but best to double check in any case.
    """
    if 'params' not in benchmark:
        # Old-format benchmarks.json
        benchmark['params'] = []
        benchmark['param_names'] = []

    msg = "Information in benchmarks.json for benchmark %s is malformed" % (
        name)
    if (not isinstance(benchmark['params'], list) or
        not isinstance(benchmark['param_names'], list)):
        raise ValueError(msg)
    if len(benchmark['params']) != len(benchmark['param_names']):
        raise ValueError(msg)
    for item in benchmark['params']:
        if not isinstance(item, list):
            raise ValueError(msg)


def safe_branch_name(branch):
    """
    Convert a branch name to a string, dealing with the None default value
    """
    if branch is None:
        # Occurs only if no branch is set in the configuration, and is
        # not visible to the user.
        return "master"
    else:
        return branch


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

        common_args.add_environment(parser)

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_conf_args(cls, conf, args):
        return cls.run(conf=conf, env_spec=args.env_spec)

    @classmethod
    def run(cls, conf, env_spec=None):
        params = {}
        graphs = {}
        date_to_hash = {}
        hash_to_date = {}
        machines = {}
        benchmark_names = set()

        log.set_nitems(5 + len(list(util.iter_subclasses(OutputPublisher))))

        if os.path.exists(conf.html_dir):
            util.long_path_rmtree(conf.html_dir)

        environments = list(environment.get_environments(conf, env_spec))
        benchmarks = Benchmarks.load(conf, environments)

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
        log.info("Getting tags and branches")
        with log.indent():
            repo = get_repo(conf)
            repo.pull()
            tags = {}
            for tag in repo.get_tags():
                log.dot()
                tags[tag] = repo.get_date_from_name(tag)

            branch_cache = BranchCache(conf, repo)

        log.step()
        log.info("Loading results")
        with log.indent():
            graph_groups = {}

            for results in iter_results(conf.results_dir):
                log.dot()
                commit_hash = results.commit_hash[:conf.hash_length]
                date_to_hash[results.date] = commit_hash
                hash_to_date[commit_hash] = results.date

                for key, val in six.iteritems(results.params):
                    params.setdefault(key, set())
                    params[key].add(val)

                for key, val in six.iteritems(results.results):
                    b = benchmarks.get(key)
                    result = compatible_results(val, b)

                    benchmark_names.add(key)

                    for branch in branch_cache.get_branches(results.commit_hash):
                        cur_params = dict(results.params)
                        cur_params['branch'] = safe_branch_name(branch)

                        graph = Graph(key, cur_params, params)
                        if graph.path in graphs:
                            graph = graphs[graph.path]
                        else:
                            graphs[graph.path] = graph
                            graph_groups.setdefault(key, []).append(graph)
                        graph.add_data_point(results.date, result)

        log.step()
        log.info("Generating graphs")
        with log.indent():
            # Generate summary graphs
            for graph_set in six.itervalues(graph_groups):
                log.dot()
                graph = make_summary_graph(graph_set)
                graphs[graph.path] = graph

            # Save files
            for graph in six.itervalues(graphs):
                log.dot()
                graph.save(conf.html_dir)

        extra_pages = []
        for cls in util.iter_subclasses(OutputPublisher):
            log.step()
            log.info("Generating output for {0}".format(cls.name))
            with log.indent():
                output_dir = os.path.join(conf.html_dir, cls.name)
                cls.publish(conf, repo, benchmarks, graphs, hash_to_date)
                extra_pages.append([cls.name, cls.button_label, cls.description])

        log.step()
        log.info("Writing index")
        benchmark_map = dict(benchmarks)
        for key in six.iterkeys(benchmark_map):
            check_benchmark_params(key, benchmark_map[key])
        for key, val in six.iteritems(params):
            val = list(val)
            val.sort(key=lambda x: x or '')
            params[key] = val
        params['branch'] = [safe_branch_name(branch) for branch in conf.branches]
        util.write_json(os.path.join(conf.html_dir, "index.json"), {
            'project': conf.project,
            'project_url': conf.project_url,
            'show_commit_url': conf.show_commit_url,
            'date_to_hash': date_to_hash,
            'params': params,
            'benchmarks': benchmark_map,
            'machines': machines,
            'tags': tags,
            'extra_pages': extra_pages,
        })
