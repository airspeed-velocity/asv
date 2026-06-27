# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Focused tests for env management extraction (design spike)."""

import os
import tempfile

import pytest

from asv.envmgmt.facade import EnvironmentFacade
from asv.envmgmt.identity import env_spec_fingerprint, requirements_fingerprint
from asv.envmgmt.matrix_pure import (
    cartesian_combinations,
    match_rule,
    parse_matrix,
    parse_rule,
)
from asv.envmgmt.virtualenv_backend import VirtualenvBackend


def test_requirements_fingerprint_order_invariant():
    a = requirements_fingerprint({"numpy": "1.26", "scipy": "1.11"})
    b = requirements_fingerprint({"scipy": "1.11", "numpy": "1.26"})
    assert a == b
    assert a != requirements_fingerprint({"numpy": "1.25", "scipy": "1.11"})


def test_env_spec_fingerprint_order_invariant():
    reqs = {"a": "1", "b": "2"}
    envs = {"FOO": "1", "BAR": "2"}
    x = env_spec_fingerprint("virtualenv", "3.11", reqs, envs)
    y = env_spec_fingerprint(
        "virtualenv",
        "3.11",
        {"b": "2", "a": "1"},
        {"BAR": "2", "FOO": "1"},
    )
    assert x == y
    assert len(x) == 24


def test_parse_matrix_and_cartesian_no_plugins():
    parsed = parse_matrix({"req:numpy": ["1.26", "1.25"], "env:OMP_NUM_THREADS": ["1"]})
    assert ("req", "numpy") in parsed
    combos = list(cartesian_combinations("3.11", parsed))
    assert len(combos) == 2
    assert all(c[("python", None)] == "3.11" for c in combos)


def test_match_rule_exact():
    target = {("python", None): "3.11", ("req", "numpy"): "1.26"}
    rule = parse_rule({"python": "3.11", "req:numpy": "1.26"})
    assert match_rule(target, rule)
    assert not match_rule(target, parse_rule({"python": "3.10"}))


def test_facade_delegates_to_backend():
    with tempfile.TemporaryDirectory() as tmp:
        backend = VirtualenvBackend(tmp, python_executable="/usr/bin/python3")
        fac = EnvironmentFacade(
            backend,
            python="3.11",
            requirements={"packaging": "23"},
            tagged_env_vars={"env:X": "1"},
        )
        assert fac.tool_name == "virtualenv"
        fp1 = fac.fingerprint()
        fp2 = fac.fingerprint()
        assert fp1 == fp2
        fac.create()
        assert backend.created
        fac.install_project("mypkg", ["pip install {wheel_file}"], {"A": "B"})
        assert backend.install_log[0][0] == "mypkg"
        out = fac.run(["-c", "print(1)"], env_vars={"Z": "1"})
        assert out["args"] == ["-c", "print(1)"]
        assert fac.python_executable() == "/usr/bin/python3"


def test_factory_still_resolves_virtualenv_and_existing():
    """Public factory compatibility — does not require full conf."""
    from asv import environment as envmod
    from asv.config import Config

    # Minimal conf object attributes used by class lookup
    conf = Config()
    # virtualenv class is registered via plugins on import
    import asv.plugins.virtualenv  # noqa: F401

    cls_v = envmod.get_environment_class_by_name("virtualenv")
    assert cls_v.tool_name == "virtualenv"
    cls_e = envmod.get_environment_class_by_name("existing")
    assert cls_e is envmod.ExistingEnvironment


def test_matrix_pure_does_not_import_plugins(monkeypatch):
    import asv.envmgmt.matrix_pure as mp
    import sys

    banned = [k for k in sys.modules if k.startswith("asv.plugins.")]
    # Module under test must not pull plugins at import time; already imported.
    src = open(mp.__file__, encoding="utf-8").read()
    assert "asv.plugins" not in src
    assert "get_environment_class" not in src
