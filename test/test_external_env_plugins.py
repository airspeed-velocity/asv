# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Optional third-party env backends via asv.environment_backends."""

import importlib.util

import pytest

from asv import environment as envmod
from asv.envmgmt import discover as disc

ASV_ENV_PLUGINS = (
    ("asv_env_conda", "conda"),
    ("asv_env_mamba", "mamba"),
    ("asv_env_rattler", "rattler"),
    ("asv_env_uv", "uv"),
    ("asv_env_pixi", "pixi"),
)


def test_core_virtualenv_existing():
    assert envmod.get_environment_class_by_name("virtualenv").tool_name == "virtualenv"
    assert envmod.get_environment_class_by_name("existing") is envmod.ExistingEnvironment


@pytest.mark.parametrize("mod,tool", ASV_ENV_PLUGINS)
def test_asv_env_plugin_is_sole_provider_when_installed(mod, tool):
    if importlib.util.find_spec(mod) is None:
        pytest.skip(f"{mod} not installed")
    disc.clear_discovery_cache()
    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
    # Must come from the package, not asv.plugins.*
    assert not cls.__module__.startswith("asv.plugins.")
    assert mod.replace("-", "_").split(".")[0] in cls.__module__ or mod in cls.__module__
