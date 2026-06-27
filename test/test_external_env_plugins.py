# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""External env plugins load via conf plugins (API-oriented where possible)."""

import sys
from pathlib import Path

import pytest

from asv import environment as envmod
from asv.plugin_manager import PluginManager

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugin_packages"


def _ensure_plugin_path():
    for sub in ("asv_conda", "asv_rattler", "asv_uv", "asv_mamba", "asv_pixi"):
        p = str(PLUGIN_ROOT / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


@pytest.fixture(scope="module")
def plugin_path():
    _ensure_plugin_path()
    yield


def test_core_only_virtualenv_and_existing(plugin_path):
    import asv.plugins.virtualenv  # noqa: F401

    assert envmod.get_environment_class_by_name("virtualenv").tool_name == "virtualenv"
    assert envmod.get_environment_class_by_name("existing") is envmod.ExistingEnvironment
    with pytest.raises(envmod.EnvironmentUnavailable):
        envmod.get_environment_class_by_name("conda")


@pytest.mark.parametrize(
    "mod,tool",
    [
        ("asv_conda", "conda"),
        ("asv_rattler", "rattler"),
        ("asv_uv", "uv"),
        ("asv_mamba", "mamba"),
    ],
)
def test_load_plugin_registers_tool(plugin_path, mod, tool):
    pm = PluginManager()
    if mod == "asv_pixi":
        pm.import_plugin("asv_rattler")
    pm.import_plugin(mod)
    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
    assert issubclass(cls, envmod.Environment)


def test_load_asv_pixi_plugin(plugin_path):
    pm = PluginManager()
    pm.import_plugin("asv_rattler")
    pm.import_plugin("asv_pixi")
    cls = envmod.get_environment_class_by_name("pixi")
    assert cls.tool_name == "pixi"


def test_all_api_plugins_register(plugin_path):
    import asv.plugins.virtualenv  # noqa: F401

    pm = PluginManager()
    for name in ("asv_conda", "asv_rattler", "asv_uv", "asv_mamba", "asv_pixi"):
        pm.import_plugin(name)
    for t in ("virtualenv", "conda", "rattler", "uv", "mamba", "pixi", "existing"):
        assert envmod.get_environment_class_by_name(t).tool_name == (
            "existing" if t == "existing" else t
        ) or (
            t == "existing"
            and envmod.get_environment_class_by_name(t) is envmod.ExistingEnvironment
        )
