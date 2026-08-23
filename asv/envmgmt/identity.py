# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Order-insensitive identity helpers for env specs (pure functions)."""

from __future__ import annotations

import hashlib
from typing import Mapping


def requirements_fingerprint(requirements: Mapping[str, str]) -> str:
    """Stable fingerprint for a requirement mapping (key order irrelevant)."""
    items = sorted((str(k), str(v)) for k, v in requirements.items())
    blob = "\0".join(f"{k}={v}" for k, v in items).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def env_spec_fingerprint(
    tool_name: str,
    python: str,
    requirements: Mapping[str, str],
    tagged_env_vars: Mapping[str, str],
    *,
    build: bool = False,
) -> str:
    """Content-addressable env identity independent of dict insertion order.

    Mirrors the intent of ``get_env_name`` hashing without depending on
    plugin modules. ``build`` selects which tagged env vars participate
    (build vs run), matching historical ASV tagging conventions when the
    caller passes already-filtered vars.
    """
    req_fp = requirements_fingerprint(requirements)
    env_items = sorted((str(k), str(v)) for k, v in tagged_env_vars.items())
    env_blob = "\0".join(f"{k}={v}" for k, v in env_items)
    payload = "|".join(
        [
            tool_name,
            python,
            req_fp,
            env_blob,
            "build" if build else "run",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
