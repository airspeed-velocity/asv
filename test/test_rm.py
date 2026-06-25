# Licensed under a 3-clause BSD style license - see LICENSE.rst
import shutil
from os.path import join

from asv import config, results

from . import tools


def test_rm(tmpdir, example_results):
    tmpdir = str(tmpdir)

    shutil.copytree(example_results, join(tmpdir, 'example_results'))

    conf = config.Config.from_json(
        {'results_dir': join(tmpdir, 'example_results'), 'repo': "### IGNORED, BUT REQUIRED ###"}
    )

    tools.run_asv_with_conf(conf, 'rm', '-y', 'benchmark=time_quantity*')

    results_a = list(results.iter_results(tmpdir))
    for result in results_a:
        for key in result.get_all_result_keys():
            assert not key.startswith('time_quantity')
        for key in result.started_at.keys():
            assert not key.startswith('time_quantity')
        for key in result.duration.keys():
            assert not key.startswith('time_quantity')

    tools.run_asv_with_conf(conf, 'rm', '-y', 'commit_hash=05d283b9')

    results_b = list(results.iter_results(tmpdir))
    assert len(results_b) == len(results_a) - 1


def test_rm_python_filter(tmpdir, example_results):
    """Regression for #1557: ``asv rm python=...`` must not use missing ``result.env``."""
    tmpdir = str(tmpdir)
    shutil.copytree(example_results, join(tmpdir, 'example_results'))

    conf = config.Config.from_json(
        {'results_dir': join(tmpdir, 'example_results'), 'repo': "### IGNORED, BUT REQUIRED ###"}
    )

    before = list(results.iter_results(join(tmpdir, 'example_results')))
    assert before, "example_results fixture should yield results"

    # Example results use python 2.7; pattern must match without AttributeError.
    tools.run_asv_with_conf(conf, 'rm', '-y', 'python=2.7')

    after = list(results.iter_results(join(tmpdir, 'example_results')))
    assert len(after) < len(before)

    # Non-matching version removes nothing (and still must not crash).
    shutil.rmtree(join(tmpdir, 'example_results'))
    shutil.copytree(example_results, join(tmpdir, 'example_results'))
    conf = config.Config.from_json(
        {'results_dir': join(tmpdir, 'example_results'), 'repo': "### IGNORED, BUT REQUIRED ###"}
    )
    n_before = len(list(results.iter_results(join(tmpdir, 'example_results'))))
    tools.run_asv_with_conf(conf, 'rm', '-y', 'python=3.12')
    n_after = len(list(results.iter_results(join(tmpdir, 'example_results'))))
    assert n_after == n_before
