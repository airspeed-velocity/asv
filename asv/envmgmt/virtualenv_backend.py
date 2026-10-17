# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Adapter: existing Virtualenv plugin surface → EnvironmentBackend protocol.

This is a *preview* adapter so reviewers can see the target shape without
rewiring all of ``asv.environment.Environment`` in one PR. Production
paths still use ``asv.plugins.virtualenv.Virtualenv`` directly.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence

from .protocol import EnvironmentBackend


class VirtualenvBackend(EnvironmentBackend):
    """Minimal backend that records operations for tests and delegates find_python."""

    tool_name = "virtualenv"

    def __init__(self, path: str, python_executable: str):
        self.path = path
        self._python_executable = python_executable
        self.created = False
        self.install_log = []

    @classmethod
    def from_python_version(cls, path: str, python: str) -> "VirtualenvBackend":
        # Lazy import keeps matrix/protocol tests free of virtualenv package.
        from asv.plugins.virtualenv import Virtualenv

        exe = Virtualenv._find_python(python)
        if exe is None:
            raise RuntimeError(f"No executable for python {python}")
        return cls(path, exe)

    def create(self) -> None:
        os.makedirs(self.path, exist_ok=True)
        self.created = True

    def install_project(
        self,
        package: str,
        install_commands: Sequence[str],
        env_vars: Mapping[str, str],
    ) -> None:
        self.install_log.append((package, list(install_commands), dict(env_vars)))

    def run(
        self,
        args: Sequence[str],
        *,
        env_vars: Optional[Mapping[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Any:
        # Preview: do not spawn processes; return the planned argv for tests.
        return {"args": list(args), "env_vars": dict(env_vars or {}), "cwd": cwd}

    def python_executable(self) -> str:
        return self._python_executable
