# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Optional HaoZeke asv_env_* plugins (separate repos, not vendored in ASV).

Install e.g. ``pip install git+https://github.com/HaoZeke/asv_env_conda.git``
and list the module in conf ``plugins``: ``["asv_env_conda"]``.
"""

import importlib

import pytest

from asv import environment as envmod
from asv.plugin_manager import PluginManager

# Shared naming: asv_env_<tool>
ASV_ENV_PLUGINS = (
    ("asv_env_conda", "conda"),
    ("asv_env_mamba", "mamba"),
    ("asv_env_rattler", "rattler"),
    ("asv_env_uv", "uv"),
    ("asv_env_pixi", "pixi"),
)


def _try_import(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def test_core_only_virtualenv_and_existing():
    import asv.plugins.virtualenv  # noqa: F401

    assert envmod.get_environment_class_by_name("virtualenv").tool_name == "virtualenv"
    assert envmod.get_environment_class_by_name("existing") is envmod.ExistingEnvironment
    with pytest.raises(envmod.EnvironmentUnavailable):
        envmod.get_environment_class_by_name("conda")


@pytest.mark.parametrize("mod,tool", ASV_ENV_PLUGINS)
def test_asv_env_plugin_registers_when_installed(mod, tool):
    if _try_import(mod) is None:
        pytest.skip(f"{mod} not installed (separate HaoZeke/{mod} repo)")
    # pixi depends on rattler module having been imported for subclass chain
    if mod == "asv_env_pixi" and _try_import("asv_env_rattler") is None:
        pytest.skip("asv_env_pixi needs asv_env_rattler installed")
    pm = PluginManager()
    if mod == "asv_env_pixi":
        pm.import_plugin("asv_env_rattler")
    pm.import_plugin(mod)
    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
