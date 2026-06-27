# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Unified environment backend discovery (envmgmt.discover) — shipped API tests."""

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

from asv import environment as envmod
from asv.config import Config
from asv.envmgmt import discover as disc


@pytest.fixture(autouse=True)
def _clear_discover_cache():
    disc.clear_discovery_cache()
    yield
    disc.clear_discovery_cache()


def test_builtin_virtualenv_resolves_without_command():
    """Library path: get_environment_class_by_name drives ensure_*."""
    cls = envmod.get_environment_class_by_name("virtualenv")
    assert cls.tool_name == "virtualenv"
    cls2 = disc.resolve_environment_class("virtualenv")
    assert cls2 is cls


def test_builtin_existing_resolves_without_command():
    cls = envmod.get_environment_class_by_name("existing")
    assert cls is envmod.ExistingEnvironment
    assert cls.tool_name == "existing"


def test_missing_type_fails_closed():
    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name("definitely_not_a_real_backend_xyz")
    msg = str(ei.value)
    assert "definitely_not_a_real_backend_xyz" in msg
    assert "Registered tool_names" in msg or "tool_names" in msg


def test_environment_type_imports_installed_conventional_module(tmp_path, monkeypatch):
    """asv_env_<type> on sys.path is imported when type is requested (no Command)."""
    tool = "discoverprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text(
        textwrap.dedent(
            f"""
            from asv import environment

            class ProbeEnv(environment.Environment):
                tool_name = {tool!r}
                matches_python_fallback = True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    # Must not be imported yet
    assert pkg not in sys.modules

    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
    assert pkg in sys.modules


def test_conf_plugins_applied_via_ensure_conf_backends(tmp_path, monkeypatch):
    """conf.plugins participates through ensure_conf_backends, not Command."""
    tool = "confprobe"
    mod_name = "conf_probe_plugin_mod"
    root = tmp_path / "site2"
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
    # Also via public factory with conf
    disc.clear_discovery_cache()
    cls2 = envmod.get_environment_class_by_name(tool, conf=conf)
    assert cls2.tool_name == tool


def test_broken_conventional_module_fails_closed(tmp_path, monkeypatch):
    tool = "brokenprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site3"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text("raise RuntimeError('boom-on-import')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(root))

    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name(tool)
    msg = str(ei.value)
    assert tool in msg
    assert "fail closed" in msg.lower() or "failed" in msg.lower()
    assert pkg in msg


def test_module_imports_but_wrong_tool_name_fails_closed(tmp_path, monkeypatch):
    tool = "wrongtoolprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site4"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text(
        textwrap.dedent(
            """
            from asv import environment

            class Wrong(environment.Environment):
                tool_name = "something_else_entirely"
                matches_python_fallback = True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))

    with pytest.raises(envmod.EnvironmentUnavailable) as ei:
        envmod.get_environment_class_by_name(tool)
    assert tool in str(ei.value)
    assert "no Environment subclass registered" in str(ei.value)


def test_get_environment_class_uses_conf_type(tmp_path, monkeypatch):
    tool = "getclsprobe"
    pkg = f"asv_env_{tool}"
    root = tmp_path / "site5"
    moddir = root / pkg
    moddir.mkdir(parents=True)
    (moddir / "__init__.py").write_text(
        textwrap.dedent(
            f"""
            from asv import environment

            class G(environment.Environment):
                tool_name = {tool!r}
                matches_python_fallback = True

                @classmethod
                def matches(cls, python):
                    return True

                def _setup(self):
                    pass
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(root))
    conf = Config()
    conf.environment_type = tool
    cls = envmod.get_environment_class(conf, "3.11")
    assert cls.tool_name == tool


def test_optional_asv_env_packages_if_installed():
    """Live HaoZeke packages when present — still via shipped resolver."""
    for mod, tool in (
        ("asv_env_conda", "conda"),
        ("asv_env_rattler", "rattler"),
        ("asv_env_uv", "uv"),
    ):
        if importlib.util.find_spec(mod) is None:
            continue
        disc.clear_discovery_cache()
        cls = envmod.get_environment_class_by_name(tool)
        assert cls.tool_name == tool
