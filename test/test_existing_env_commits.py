# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Existing environment + commit range labeling (issue #1464)."""

import sys
from pathlib import Path

from asv import config
from asv.commands import run as run_mod
from asv.environment import ExistingEnvironment


def test_existing_only_range_no_longer_banned_in_source():
    src = Path(run_mod.__file__).read_text(encoding="utf-8")
    assert "No range spec may be specified if benchmarking in" not in src
    assert "commit range labels results" in src


def test_existing_env_skips_install_list():
    conf = config.Config()
    conf.env_dir = "/tmp/asv-x"
    conf.project = "x"
    conf.repo = "."
    env = ExistingEnvironment(conf, sys.executable, {}, {})
    assert env.can_install_project() is False
    assert env.tool_name == "existing"
