# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Environment management extraction (design spike).

Public symbols for the backend boundary. Legacy code still lives in
``asv.environment``; this package owns **backend discovery** via
:mod:`asv.envmgmt.discover` so ``environment_type`` resolves without
going through ``Command``.
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
