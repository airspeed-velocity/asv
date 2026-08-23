# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Environment management: discovery (production) and lifecycle spike.

Discovery (:mod:`asv.envmgmt.discover`) is the host-side resolver for
``environment_type``. Matrix layers (:mod:`asv.envmgmt.matrix_layers`)
document how conf ``matrix`` constraints relate to create vs project
install. Protocol/facade modules are a longer-term lifecycle spike and
are not required for discovery.
"""

from .discover import (
    ENTRY_POINT_GROUP,
    ensure_conf_backends,
    ensure_environment_backend,
    resolve_environment_class,
)
from .identity import env_spec_fingerprint, requirements_fingerprint
from .matrix_layers import (
    KNOWN_BACKEND_CAPABILITIES,
    LAYER_HOST,
    LAYER_MATRIX,
    LAYER_PROJECT,
    LAYER_RUNTIME,
    backend_capabilities,
    matrix_means_something_checklist,
    recommend_install_command,
)
from .protocol import EnvironmentBackend

__all__ = [
    "EnvironmentBackend",
    "ENTRY_POINT_GROUP",
    "LAYER_HOST",
    "LAYER_MATRIX",
    "LAYER_PROJECT",
    "LAYER_RUNTIME",
    "KNOWN_BACKEND_CAPABILITIES",
    "backend_capabilities",
    "env_spec_fingerprint",
    "requirements_fingerprint",
    "ensure_conf_backends",
    "ensure_environment_backend",
    "resolve_environment_class",
    "matrix_means_something_checklist",
    "recommend_install_command",
]
