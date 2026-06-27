# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Environment management extraction (design spike).

Public symbols for the backend boundary. Legacy code still lives in
``asv.environment``; this package shows the target seams.
"""

from .identity import env_spec_fingerprint, requirements_fingerprint
from .protocol import EnvironmentBackend

__all__ = [
    "EnvironmentBackend",
    "env_spec_fingerprint",
    "requirements_fingerprint",
]
