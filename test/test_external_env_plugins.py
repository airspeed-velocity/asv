# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""External env plugins (asv_conda / asv_rattler / asv_uv / asv_mamba) loadable via conf plugins."""

import importlib
import sys
from pathlib import Path

import pytest

from asv import environment as envmod
from asv.plugin_manager import PluginManager

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugin_packages"


def _ensure_plugin_path():
    # Allow importing packages from plugin_packages/*/ without install
    for sub in ("asv_conda", "asv_rattler", "asv_uv", "asv_mamba"):
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


def test_load_asv_conda_plugin(plugin_path):
    pm = PluginManager()
    pm.import_plugin("asv_conda")
    cls = envmod.get_environment_class_by_name("conda")
    assert cls.tool_name == "conda"
    assert issubclass(cls, envmod.Environment)


def test_load_asv_rattler_plugin(plugin_path):
    pm = PluginManager()
    pm.import_plugin("asv_rattler")
    cls = envmod.get_environment_class_by_name("rattler")
    assert cls.tool_name == "rattler"


def test_load_asv_uv_plugin(plugin_path):
    pm = PluginManager()
    pm.import_plugin("asv_uv")
    cls = envmod.get_environment_class_by_name("uv")
    assert cls.tool_name == "uv"


def test_load_asv_mamba_plugin(plugin_path):
    pm = PluginManager()
    pm.import_plugin("asv_conda")
    pm.import_plugin("asv_mamba")
    cls = envmod.get_environment_class_by_name("mamba")
    assert cls.tool_name == "mamba"


def test_all_plugins_together(plugin_path):
    pm = PluginManager()
    for name in ("asv_conda", "asv_rattler", "asv_uv", "asv_mamba"):
        pm.import_plugin(name)
    tools = {
        envmod.get_environment_class_by_name(t).tool_name
        for t in ("virtualenv", "conda", "rattler", "uv", "mamba", "existing")
    }
    # virtualenv from core import
    import asv.plugins.virtualenv  # noqa: F401

    assert tools == {"virtualenv", "conda", "rattler", "uv", "mamba", "existing"}
