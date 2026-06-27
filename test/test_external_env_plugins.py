# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Optional HaoZeke asv_env_* plugins (separate repos, not vendored in ASV).

Discovery is via :mod:`asv.envmgmt.discover` / ``get_environment_class_by_name``
— no Command required. Install e.g.::

    pip install git+https://github.com/HaoZeke/asv_env_conda.git
"""

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


def test_core_only_virtualenv_and_existing():
    assert envmod.get_environment_class_by_name("virtualenv").tool_name == "virtualenv"
    assert envmod.get_environment_class_by_name("existing") is envmod.ExistingEnvironment
    with pytest.raises(envmod.EnvironmentUnavailable):
        envmod.get_environment_class_by_name("conda_not_installed_xyz_unique")


@pytest.mark.parametrize("mod,tool", ASV_ENV_PLUGINS)
def test_asv_env_plugin_resolves_when_installed(mod, tool):
    if importlib.util.find_spec(mod) is None:
        pytest.skip(f"{mod} not installed (separate HaoZeke/{mod} repo)")
    if mod == "asv_env_pixi" and importlib.util.find_spec("asv_env_rattler") is None:
        pytest.skip("asv_env_pixi needs asv_env_rattler installed")
    disc.clear_discovery_cache()
    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
