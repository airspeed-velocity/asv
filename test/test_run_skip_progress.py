# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Progress accounting for asv run -k (issue #918)."""

from collections import defaultdict


def _count_active_steps(commit_hashes, environments, benchmarks, skipped_benchmarks):
    """Mirror of run.py active-step counting (keep in sync)."""
    steps = 0
    for commit_hash in commit_hashes:
        if commit_hash in skipped_benchmarks and skipped_benchmarks[commit_hash] is True:
            continue
        for env in environments:
            skip_list = skipped_benchmarks[(commit_hash, env)]
            for bench in benchmarks:
                if bench not in skip_list:
                    steps += 1
    return steps


def test_skip_existing_reduces_step_count():
    commits = ["a", "b", "c"]
    envs = ["e1"]
    benches = ["t1", "t2"]
    skipped = defaultdict(set)
    assert _count_active_steps(commits, envs, benches, skipped) == 6
    skipped["b"] = True
    assert _count_active_steps(commits, envs, benches, skipped) == 4
    skipped = defaultdict(set)
    skipped[("a", "e1")].add("t1")
    assert _count_active_steps(commits, envs, benches, skipped) == 5
