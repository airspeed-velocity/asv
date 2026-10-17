# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Formal environment *layers* and matrix install modes.

Addresses the product problems in upstream issues:

- `#1542`_ How to make ``matrix`` mean anything?
- `#1543`_ Solve PyPI together with conda when possible
- `#1436`_ RFC: resolvers and environment management

Layers (bottom → top)
---------------------
1. **host** — operator process: ``asv`` + optional backend package
   (discovered via :mod:`asv.envmgmt.discover`).
2. **matrix** — Python version + conf ``matrix`` requirements / env vars.
   Ideally one solver call owns this layer.
3. **project** — the package under test (built wheel / install_command).
4. **runtime** — execute benchmarks (``asv_runner``, process isolation).

A matrix only "means something" when constraints from layer 2 still hold
after layer 3. That fails when create installs conda packages and a later
``pip install`` ignores those pins (classic conda+pip footgun).

Install modes (backend capability)
----------------------------------
- ``create``: matrix specs fold into the environment *create* solve
  (rattler/pixi/conda create, uv create + pip install of matrix reqs).
- ``post``: matrix applied as a second mutation after create
  (legacy ``conda env update`` style).
- ``joint``: single solve of matrix + project artifact (wheel/sdist).
  This is the only fully correct mode for mixed ecosystems when the
  solver supports it (pixi today; rattler when
  https://github.com/conda/rattler/issues/1044 lands).

Backends declare capabilities via class attributes on their
``Environment`` subclass (see :data:`CAPABILITY_ATTRS`). Core and
docs use these flags; they do not auto-change ``install_command``.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

# Layer names (stable strings for docs, SBOM tags, and future APIs).
LAYER_HOST = "host"
LAYER_MATRIX = "matrix"
LAYER_PROJECT = "project"
LAYER_RUNTIME = "runtime"

LAYERS: Tuple[str, ...] = (
    LAYER_HOST,
    LAYER_MATRIX,
    LAYER_PROJECT,
    LAYER_RUNTIME,
)

# How matrix requirements enter the prefix.
MATRIX_INSTALL_CREATE = "create"
MATRIX_INSTALL_POST = "post"
MATRIX_INSTALL_JOINT = "joint"

MATRIX_INSTALL_MODES: Tuple[str, ...] = (
    MATRIX_INSTALL_CREATE,
    MATRIX_INSTALL_POST,
    MATRIX_INSTALL_JOINT,
)

# Class attribute names backends may set on Environment subclasses.
CAPABILITY_ATTRS: Tuple[str, ...] = (
    "matrix_install_mode",
    "supports_joint_pypi_conda_solve",
    "supports_joint_pypi_solve",
    "project_install_prefers_no_deps",
    "requires_host_tool",
)

# Defaults matching historical ASV: matrix reqs at create, project via
# install_command (often `pip install {wheel_file}`) without re-solving.
DEFAULT_CAPABILITIES: Dict[str, Any] = {
    "matrix_install_mode": MATRIX_INSTALL_CREATE,
    "supports_joint_pypi_conda_solve": False,
    "supports_joint_pypi_solve": False,
    "project_install_prefers_no_deps": False,
    "requires_host_tool": None,
}

# Known out-of-tree / built-in tool_name → documented capabilities.
# Packages should set the same attributes on their Environment subclass;
# this table is the design-branch reference for docs and tests.
KNOWN_BACKEND_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "virtualenv": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        "supports_joint_pypi_conda_solve": False,
        "supports_joint_pypi_solve": True,  # all matrix specs are PyPI
        "project_install_prefers_no_deps": True,
        "requires_host_tool": None,
    },
    "existing": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        "supports_joint_pypi_conda_solve": False,
        "supports_joint_pypi_solve": False,
        "project_install_prefers_no_deps": False,
        "requires_host_tool": None,
    },
    "uv": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        "supports_joint_pypi_conda_solve": False,
        "supports_joint_pypi_solve": True,
        "project_install_prefers_no_deps": True,
        "requires_host_tool": None,  # in-process crates
    },
    "conda": {
        "matrix_install_mode": MATRIX_INSTALL_POST,  # env create then often update
        "supports_joint_pypi_conda_solve": False,
        "supports_joint_pypi_solve": False,
        "project_install_prefers_no_deps": False,
        "requires_host_tool": "conda",
    },
    "mamba": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        "supports_joint_pypi_conda_solve": False,
        "supports_joint_pypi_solve": False,
        "project_install_prefers_no_deps": False,
        "requires_host_tool": "mamba",
    },
    "rattler": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        "supports_joint_pypi_conda_solve": False,  # blocked on rattler#1044
        "supports_joint_pypi_solve": False,
        "project_install_prefers_no_deps": True,  # conda-only matrix then pip no-deps
        "requires_host_tool": None,
    },
    "pixi": {
        "matrix_install_mode": MATRIX_INSTALL_CREATE,
        # pixi can joint-solve conda+pypi when pypi-deps are in the manifest;
        # ASV path does not yet pass the project wheel into that solve.
        "supports_joint_pypi_conda_solve": True,
        "supports_joint_pypi_solve": True,
        "project_install_prefers_no_deps": True,
        "requires_host_tool": "pixi",
    },
}


def backend_capabilities(tool_name: str, cls: Any = None) -> Dict[str, Any]:
    """Resolve capability flags for *tool_name*, preferring *cls* attributes."""
    caps = dict(DEFAULT_CAPABILITIES)
    known = KNOWN_BACKEND_CAPABILITIES.get(tool_name)
    if known:
        caps.update(known)
    if cls is not None:
        for attr in CAPABILITY_ATTRS:
            if hasattr(cls, attr):
                caps[attr] = getattr(cls, attr)
    return caps


def recommend_install_command(tool_name: str, cls: Any = None) -> Optional[Sequence[str]]:
    """Suggested ``install_command`` so matrix constraints stay meaningful.

    Returns a command list when the backend prefers no-deps project install,
    else ``None`` (keep ASV default).
    """
    caps = backend_capabilities(tool_name, cls)
    if caps.get("project_install_prefers_no_deps"):
        return ["in-dir={env_dir} python -mpip install --no-deps {wheel_file}"]
    return None


def matrix_means_something_checklist(tool_name: str, conf: Any = None) -> Mapping[str, str]:
    """Human-oriented checklist for whether conf matrix constraints hold.

    Values are short status strings, not pass/fail booleans, so docs and
    CLI can print them without inventing green-check theatre.
    """
    caps = backend_capabilities(tool_name)
    mode = caps["matrix_install_mode"]
    joint = caps["supports_joint_pypi_conda_solve"]
    no_deps = caps["project_install_prefers_no_deps"]

    install_cmd = None
    if conf is not None:
        install_cmd = getattr(conf, "install_command", None)

    notes = {
        "matrix_layer": (
            f"mode={mode}: matrix specs enter prefix at create"
            if mode == MATRIX_INSTALL_CREATE
            else (
                f"mode={mode}: matrix may be a second mutation "
                "(constraints can drift)"
                if mode == MATRIX_INSTALL_POST
                else f"mode={mode}: single solve of matrix + project"
            )
        ),
        "joint_conda_pypi": (
            "backend can joint-solve conda+PyPI when the project is passed "
            "into the solve (ASV joint path is opt-in / future)"
            if joint
            else "backend cannot joint-solve conda+PyPI; keep pip+ specs "
            "minimal or use pixi / wait for rattler joint solve"
        ),
        "project_layer": (
            "prefer install_command with --no-deps so project install "
            "does not rewrite matrix pins"
            if no_deps
            else "project install may pull transitive deps; pin them in "
            "matrix or use a joint-capable backend"
        ),
    }
    if install_cmd is not None:
        joined = " ".join(install_cmd) if isinstance(install_cmd, (list, tuple)) else str(install_cmd)
        if no_deps and "--no-deps" not in joined and joined.strip():
            notes["install_command"] = (
                "current install_command does not use --no-deps; "
                "matrix pins may be overwritten by project deps"
            )
        elif not joined.strip():
            notes["install_command"] = (
                "empty install_command: only valid when project is installed "
                "inside the matrix/joint solve"
            )
        else:
            notes["install_command"] = "install_command set by conf"
    return notes


__all__ = [
    "LAYER_HOST",
    "LAYER_MATRIX",
    "LAYER_PROJECT",
    "LAYER_RUNTIME",
    "LAYERS",
    "MATRIX_INSTALL_CREATE",
    "MATRIX_INSTALL_POST",
    "MATRIX_INSTALL_JOINT",
    "MATRIX_INSTALL_MODES",
    "CAPABILITY_ATTRS",
    "DEFAULT_CAPABILITIES",
    "KNOWN_BACKEND_CAPABILITIES",
    "backend_capabilities",
    "recommend_install_command",
    "matrix_means_something_checklist",
]
