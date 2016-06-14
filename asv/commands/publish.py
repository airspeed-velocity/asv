# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
import multiprocessing

import six

from . import Command
from ..benchmarks import Benchmarks
from ..console import log
from ..graph import GraphSet
from ..machine import iter_machine_files
from ..repo import get_repo
from ..results import iter_results, compatible_results
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
        graphs = GraphSet()
        machines = {}
        benchmark_names = set()

        log.set_nitems(6 + len(list(util.iter_subclasses(OutputPublisher))))

        if os.path.exists(conf.html_dir):
            util.long_path_rmtree(conf.html_dir)

        environments = list(environment.get_environments(conf, env_spec))
        repo = get_repo(conf)
        benchmarks = Benchmarks.load(conf, repo, environments)

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
        log.info("Getting params, commits, tags and branches")
        with log.indent():
            # Determine first the set of all parameters and all commits
            hash_to_date = {}
            for results in iter_results(conf.results_dir):
                hash_to_date[results.commit_hash] = results.date
                for key, val in six.iteritems(results.params):
                    if val is None:
                        # Backward compatibility -- null means ''
                        val = ''

                    params.setdefault(key, set())
                    params[key].add(val)

            repo.pull()
            tags = repo.get_tags()
            revisions = repo.get_revisions(set(hash_to_date.keys()) | set(tags.values()))

            for tag, commit_hash in list(tags.items()):
                # Map to revision number instead of commit hash and add tags to hash_to_date
                tags[tag] = revisions[tags[tag]]
                hash_to_date[commit_hash] = repo.get_date_from_name(commit_hash)

            revision_to_date = dict((r, hash_to_date[h]) for h, r in six.iteritems(revisions))

            branches = dict(
                (branch, repo.get_branch_commits(branch))
                for branch in conf.branches)

        log.step()
        log.info("Loading results")
        with log.indent():
            # Generate all graphs
            for results in iter_results(conf.results_dir):
                log.dot()

                for key, val in six.iteritems(results.results):
                    b = benchmarks.get(key)
                    result = compatible_results(val, b)

                    benchmark_names.add(key)

                    for branch in [
                        branch for branch, commits in branches.items()
                        if results.commit_hash in commits
                    ]:
                        cur_params = dict(results.params)
                        cur_params['branch'] = repo.get_branch_name(branch)

                        # Backward compatibility, see above
                        for param_key, param_value in list(cur_params.items()):
                            if param_value is None:
                                cur_params[param_key] = ''

                        # Fill in missing params
                        for param_key in params.keys():
                            if param_key not in cur_params:
                                cur_params[param_key] = None
                                params[param_key].add(None)

                        # Create graph
                        graph = graphs.get_graph(key, cur_params)
                        graph.add_data_point(revisions[results.commit_hash], result)

            # Get the parameter sets for all graphs
            graph_param_list = []
            for path, graph in graphs:
                if 'summary' not in graph.params:
                    if graph.params not in graph_param_list:
                        graph_param_list.append(graph.params)

        log.step()
        log.info("Detecting steps")
        with log.indent():
            n_processes = multiprocessing.cpu_count()
            pool = multiprocessing.Pool(n_processes)
            try:
                graphs.detect_steps(pool, dots=log.dot)
            finally:
                pool.terminate()

        log.step()
        log.info("Generating graphs")
        with log.indent():
            # Save files
            graphs.save(conf.html_dir, dots=log.dot)

        pages = []
        classes = sorted(util.iter_subclasses(OutputPublisher),
                         key=lambda cls: cls.order)
        for cls in classes:
            log.step()
            log.info("Generating output for {0}".format(cls.__name__))
            with log.indent():
                cls.publish(conf, repo, benchmarks, graphs, revisions)
                pages.append([cls.name, cls.button_label, cls.description])

        log.step()
        log.info("Writing index")
        benchmark_map = dict(benchmarks)
        for key in six.iterkeys(benchmark_map):
            check_benchmark_params(key, benchmark_map[key])
        for key, val in six.iteritems(params):
            val = list(val)
            val.sort(key=lambda x: '[none]' if x is None else str(x))
            params[key] = val
        params['branch'] = [repo.get_branch_name(branch) for branch in conf.branches]
        revision_to_hash = dict((r, h) for h, r in six.iteritems(revisions))
        util.write_json(os.path.join(conf.html_dir, "index.json"), {
            'project': conf.project,
            'project_url': conf.project_url,
            'show_commit_url': conf.show_commit_url,
            'hash_length': conf.hash_length,
            'revision_to_hash': revision_to_hash,
            'revision_to_date': revision_to_date,
            'params': params,
            'graph_param_list': graph_param_list,
            'benchmarks': benchmark_map,
            'machines': machines,
            'tags': tags,
            'pages': pages,
        })
