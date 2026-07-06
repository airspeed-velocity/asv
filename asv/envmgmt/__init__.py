# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Environment management: discovery (production) and lifecycle spike.

Discovery (:mod:`asv.envmgmt.discover`) is the host-side resolver for
``environment_type``. Protocol/facade modules are a longer-term lifecycle
spike and are not required for discovery.
"""

from .discover import (
    ENTRY_POINT_GROUP,
    ensure_conf_backends,
    ensure_environment_backend,
    resolve_environment_class,
)
from .identity import env_spec_fingerprint, requirements_fingerprint
from .protocol import EnvironmentBackend

__all__ = [
    "EnvironmentBackend",
    "ENTRY_POINT_GROUP",
    "env_spec_fingerprint",
    "requirements_fingerprint",
    "ensure_conf_backends",
    "ensure_environment_backend",
    "resolve_environment_class",
]
