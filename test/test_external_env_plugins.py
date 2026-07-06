# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Optional third-party env backends (entry points / packages).

Packages provide group ``asv.environment_backends``. The conventional
``asv_env_*`` module names remain a transitional fallback only when
``ASV_ENV_LEGACY_MODULE_FALLBACK`` is enabled.
"""

import importlib.util
import os

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
def test_asv_env_plugin_resolves_when_installed(mod, tool, monkeypatch):
    if importlib.util.find_spec(mod) is None:
        pytest.skip(f"{mod} not installed")
    # Prefer entry points; enable legacy module fallback for older packages
    # that only ship module EPs under asv.plugins or plain modules.
    monkeypatch.setenv("ASV_ENV_LEGACY_MODULE_FALLBACK", "1")
    disc.clear_discovery_cache()
    # In-tree tool of same name may win for conda/rattler/uv on Stage 1
    cls = envmod.get_environment_class_by_name(tool)
    assert cls.tool_name == tool
