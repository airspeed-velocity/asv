# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""ASV environment plugin: mamba (conda-compatible CLI via CONDA_EXE / mamba on PATH)."""

import os

from asv import environment, util
from asv.console import log

# Re-use conda backend implementation when asv_conda is installed.
try:
    from asv_conda import Conda as _CondaBase
    from asv_conda import _conda_lock, _dummy_lock, _find_conda as _find_conda_base
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "asv_mamba requires asv_conda (pip install asv_conda / plugin_packages/asv_conda)"
    ) from exc


def _find_mamba():
    if "CONDA_EXE" in os.environ and "mamba" in os.environ["CONDA_EXE"]:
        return os.environ["CONDA_EXE"]
    try:
        return util.which("mamba")
    except OSError:
        return _find_conda_base()


class Mamba(_CondaBase):
    """Same as conda backend, but prefers the ``mamba`` executable."""

    tool_name = "mamba"

    def _run_conda(self, args, env=None):
        # Parent uses _find_conda; monkeypatch for this call chain.
        import asv_conda as ac

        real = ac._find_conda
        ac._find_conda = _find_mamba
        try:
            return super()._run_conda(args, env=env)
        finally:
            ac._find_conda = real


# Keep module-level names for tests / discovery
_find_conda = _find_mamba
