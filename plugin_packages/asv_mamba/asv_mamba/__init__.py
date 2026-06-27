# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""ASV environment backend using **libmamba** (in-process API), not the conda CLI.

Requires ``libmambapy`` (typically from conda-forge: ``conda install -c conda-forge libmambapy``).
Falls back is **not** implemented — shell/CLI belongs in ``asv_conda``.
"""

from __future__ import annotations

import os
from pathlib import Path

from asv import environment, util
from asv.console import log

try:
    import libmambapy as mamba
except ImportError:  # pragma: no cover
    mamba = None


class Mamba(environment.Environment):
    """Create/solve environments via libmambapy (API-oriented)."""

    tool_name = "mamba"

    def __init__(self, conf, python, requirements, tagged_env_vars):
        if mamba is None:
            raise environment.EnvironmentUnavailable(
                "asv_mamba requires libmambapy (install from conda-forge); "
                "for the classic conda CLI use asv_conda instead"
            )
        self._python = python
        self._requirements = requirements
        self._channels = list(conf.conda_channels or [])
        if "conda-forge" not in self._channels:
            self._channels.append("conda-forge")
        super().__init__(conf, python, requirements, tagged_env_vars)
        self._prefix = Path(self._path)

    @classmethod
    def matches(cls, python):
        if mamba is None:
            return False
        import re

        return bool(re.match(r"^[0-9].*$", python) or re.match(r"^pypy[0-9.]*$", python))

    def _spec_list(self):
        specs = [f"python={self._python}", "pip", "wheel"]
        for key, val in {**self._requirements, **self._base_requirements}.items():
            if key.startswith("pip+"):
                continue  # pip-only; installed after prefix exists
            if val:
                specs.append(f"{key}={val}")
            else:
                specs.append(key)
        return specs

    def _setup(self):
        log.info(f"Creating libmamba environment for {self.name}")
        self._prefix.mkdir(parents=True, exist_ok=True)
        # Context + channel setup (libmambapy API; version-sensitive)
        Context = getattr(mamba, "Context", None)
        if Context is not None:
            ctx = Context()
            # Best-effort channel list
            try:
                ctx.channels = self._channels
            except Exception:
                pass
        ChannelContext = getattr(mamba, "ChannelContext", None)
        Pool = getattr(mamba, "Pool", None)
        Solver = getattr(mamba, "Solver", None)
        PrefixData = getattr(mamba, "PrefixData", None)
        SubdirData = getattr(mamba, "SubdirData", None)
        Transaction = getattr(mamba, "Transaction", None)
        # Prefer high-level helpers if present (varies by libmambapy version)
        create_or_update = (
            getattr(mamba, "create", None)
            or getattr(mamba, "install", None)
        )
        specs = self._spec_list()
        if callable(create_or_update) and create_or_update is not getattr(mamba, "install", None):
            create_or_update(str(self._prefix), specs, channels=self._channels)
        elif Solver is not None and Pool is not None:
            # Minimal solve/transaction path — exact API differs; fail clearly if incomplete
            raise environment.EnvironmentUnavailable(
                "libmambapy is importable but this asv_mamba build needs a "
                "libmambapy version exposing a high-level create/install helper; "
                "upgrade libmambapy or use asv_rattler (py-rattler API)"
            )
        else:
            raise environment.EnvironmentUnavailable(
                "libmambapy API surface not recognized; use asv_rattler or asv_conda"
            )
        # pip+ requirements via python -m pip inside the prefix (interpreter API/subprocess to python)
        self._install_pip_requirements()

    def _install_pip_requirements(self):
        pip_args = []
        for key, val in {**self._requirements, **self._base_requirements}.items():
            if key.startswith("pip+"):
                pip_args.append(f"{key[4:]} {val}" if val else key[4:])
        if not pip_args:
            return
        py = self._prefix / ("python.exe" if os.name == "nt" else "bin/python")
        if not py.is_file():
            # try nested
            for cand in self._prefix.rglob("python*"):
                if cand.is_file() and "python" in cand.name:
                    py = cand
                    break
        for declaration in pip_args:
            parsed = util.ParsedPipDeclaration(declaration)
            # Use environment helper if present
            if hasattr(self, "_run_pip"):
                util.construct_pip_call(self._run_pip, parsed)()
            else:
                util.check_call(
                    [str(py), "-m", "pip", "install", "-v"]
                    + ([f"{parsed.pkg}=={parsed.version}"] if getattr(parsed, "version", None) else [parsed.pkg]),
                )

    def run(self, args, **kwargs):
        return self.run_executable("python", args, **kwargs)
