# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
import itertools

import six
from six.moves import zip as izip

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..graph import Graph
from ..machine import iter_machine_files
from ..repo import get_repo
from ..results import iter_results
from ..branch_cache import BranchCache
from .. import util


def compatible_results(result, benchmark):
    """
    Obtain values from *result* that are compatible with
    parameters of *benchmark*
    """
    if not benchmark or not benchmark.get('params'):
        # Not a parameterized benchmark, or a benchmark that is not
        # currently there. The javascript side doesn't know how to
        # visualize benchmarks unless the params are the same as those
        # of the current benchmark. Single floating point values are
        # OK, but not parameterized ones.
        if isinstance(result, dict):
            return None
        else:
            return result

    if result is None:
        # All results missing, eg. build failure
        return result

    if not isinstance(result, dict) or 'params' not in result:
        # Not a parameterized result -- test probably was once
        # non-parameterized
        return None

    # Pick results for those parameters that also appear in the
    # current benchmark
    old_results = {}
    for param, value in izip(itertools.product(*result['params']),
                             result['result']):
        old_results[param] = value

    new_results = []
    for param in itertools.product(*benchmark['params']):
        new_results.append(old_results.get(param))
    return new_results


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
            for results in iter_results(conf.results_dir):
                log.dot()
                date_to_hash[results.date] = results.commit_hash[
                    :conf.hash_length]

                for key, val in six.iteritems(results.params):
                    params.setdefault(key, set())
                    params[key].add(val)

                for key, val in six.iteritems(results.results):
                    b = benchmarks.get(key)
                    result = compatible_results(val, b)

                    benchmark_names.add(key)

                    for branch in branch_cache.get_branches(results.commit_hash):
                        cur_params = dict(results.params)
                        cur_params['branch'] = branch if branch is not None else "master"

                        graph = Graph(key, cur_params, params)
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
        log.info("Writing index")
        benchmark_map = dict(benchmarks)
        for key in six.iterkeys(benchmark_map):
            check_benchmark_params(key, benchmark_map[key])
        for key, val in six.iteritems(params):
            val = list(val)
            val.sort(key=lambda x: x or '')
            params[key] = val
        params['branch'] = conf.branches  # maintain same order as in conf file
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
