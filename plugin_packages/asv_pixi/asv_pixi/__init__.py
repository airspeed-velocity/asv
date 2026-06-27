# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""ASV environment plugin for pixi (API-oriented; not shelling out to `pixi` CLI by default).

This is a **skeleton** on the design branch: registers ``environment_type = "pixi"``
and fails clearly until wired to pixi/lib APIs. Prefer in-process bindings over
subprocess for solves (see internal design note on API vs shell backends).
"""

from asv import environment


class Pixi(environment.Environment):
    """Pixi-backed environment (placeholder for Rust/Python API integration)."""

    tool_name = "pixi"
    matches_python_fallback = False

    def __init__(self, conf, python, requirements, tagged_env_vars):
        raise environment.EnvironmentUnavailable(
            "asv_pixi is a design-branch stub: wire pixi/lib APIs before use "
            "(not the pixi CLI). Install is a no-op until implemented."
        )

    @classmethod
    def matches(cls, python):
        return False
