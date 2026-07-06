# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Host-side environment backend discovery (asv.envmgmt.discover)."""

import sys
import textwrap
import warnings
from pathlib import Path

import pytest

from asv import environment as envmod
from asv.config import Config
from asv.envmgmt import discover as disc


@pytest.fixture(autouse=True)
def _clear_discover_cache(monkeypatch):
    disc.clear_discovery_cache()
    # Stage-1 tests: no legacy module fallback unless a test opts in
    monkeypatch.delenv("ASV_ENV_LEGACY_MODULE_FALLBACK", raising=False)
    yield
    disc.clear_discovery_cache()


def test_entry_point_group_name():
    assert disc.ENTRY_POINT_GROUP == "asv.environment_backends"


def test_builtin_virtualenv_and_existing():
    assert envmod.get_environment_class_by_name("virtualenv").tool_name == "virtualenv"
    assert envmod.get_environment_class_by_name("existing") is envmod.ExistingEnvironment


def test_empty_type_defaults_virtualenv():
    cls = disc.ensure_environment_backend("")
    assert cls.tool_name == "virtualenv"


def test_missing_type_fails_closed_without_haozeeke_url():
    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name("definitely_not_a_real_backend_xyz")
    msg = str(ei.value)
    assert "definitely_not_a_real_backend_xyz" in msg
    assert "asv.environment_backends" in msg
    assert "HaoZeke" not in msg
    assert "git+https" not in msg


def test_in_tree_conda_still_resolves_when_present():
    """Stage 1: optional in-tree backends remain available."""
    try:
        import asv.plugins.conda  # noqa: F401
    except Exception:
        pytest.skip("conda plugin not importable in this environment")
    disc.clear_discovery_cache()
    cls = envmod.get_environment_class_by_name("conda")
    assert cls.tool_name == "conda"


def test_conf_plugins_via_ensure_conf_backends(tmp_path, monkeypatch):
    tool = "confprobe"
    mod_name = "conf_probe_plugin_mod_asv"
    root = tmp_path / "site"
    root.mkdir()
    (root / f"{mod_name}.py").write_text(
        textwrap.dedent(
            f"""
            from asv import environment

            class ConfProbe(environment.Environment):
                tool_name = {tool!r}
                matches_python_fallback = True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    conf = Config()
    conf.environment_type = tool
    conf.plugins = [mod_name]
    cls = disc.ensure_conf_backends(conf)
    assert cls.tool_name == tool


def test_legacy_module_fallback_opt_in(tmp_path, monkeypatch):
    tool = "legacyprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text(
        textwrap.dedent(
            f"""
            from asv import environment

            class Legacy(environment.Environment):
                tool_name = {tool!r}
                matches_python_fallback = True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.setenv("ASV_ENV_LEGACY_MODULE_FALLBACK", "1")
    disc.clear_discovery_cache()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
    assert any("transitional" in str(x.message).lower() or "legacy" in str(x.message).lower()
               or "ASV_ENV" in str(x.message) or "entry point" in str(x.message).lower()
               for x in w)


def test_legacy_module_fallback_off_by_default(tmp_path, monkeypatch):
    tool = "legacyoffprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text(
        textwrap.dedent(
            f"""
            from asv import environment

            class Legacy(environment.Environment):
                tool_name = {tool!r}
                matches_python_fallback = True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    disc.clear_discovery_cache()
    with pytest.raises(envmod.EnvironmentUnavailable):
        envmod.get_environment_class_by_name(tool)


def test_broken_legacy_module_fails_closed_when_enabled(tmp_path, monkeypatch):
    tool = "brokenlegacy"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.setenv("ASV_ENV_LEGACY_MODULE_FALLBACK", "1")
    disc.clear_discovery_cache()
    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name(tool)
    assert "fail closed" in str(ei.value).lower() or "failed" in str(ei.value).lower()


def test_duplicate_entry_points_fail_closed(monkeypatch):
    """Two providers for the same environment_type must not pick arbitrarily."""

    class _FakeDist:
        def __str__(self):
            return "fake-dist"

    class _FakeEP:
        def __init__(self, name, value):
            self.name = name
            self.value = value
            self.dist = _FakeDist()

        def load(self):
            raise AssertionError("must not load when duplicates exist")

    tool = "dupetype"
    fake = [
        _FakeEP(tool, "pkg_a:BackendA"),
        _FakeEP(tool, "pkg_b:BackendB"),
    ]

    def _fake_iter(group):
        if group == disc.ENTRY_POINT_GROUP:
            return fake
        return []

    monkeypatch.setattr(disc, "_iter_entry_points", _fake_iter)
    disc.clear_discovery_cache()
    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name(tool)
    msg = str(ei.value)
    assert "Multiple entry points" in msg
    assert tool in msg
