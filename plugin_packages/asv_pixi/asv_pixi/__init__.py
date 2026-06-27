# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""ASV environment backend oriented at the **pixi stack APIs**.

There is no supported in-process ``pixi`` Python package on PyPI for project
management (the ``pixi`` name on PyPI is unrelated). Pixi's solver/installer
stack is **rattler**; this plugin therefore drives **py-rattler** APIs
(``solve`` / ``install``) under ``environment_type = "pixi"``.

Do **not** shell out to the ``pixi`` CLI here.
"""

from __future__ import annotations

# Re-export Rattler implementation under tool_name pixi
try:
    from asv_rattler import Rattler as _RattlerBase
    from asv_rattler import _HAS_RATTLER
except ImportError as exc:  # pragma: no cover
    raise ImportError("asv_pixi requires asv_rattler (py-rattler API backend)") from exc

from asv import environment


class Pixi(_RattlerBase):
    """Same API path as asv_rattler, distinct tool_name for matrix / conf."""

    tool_name = "pixi"

    def __init__(self, conf, python, requirements, tagged_env_vars):
        if not _HAS_RATTLER:
            raise environment.EnvironmentUnavailable(
                "asv_pixi needs py-rattler (API); install py-rattler / asv_rattler deps"
            )
        super().__init__(conf, python, requirements, tagged_env_vars)
