# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Thin orchestration facade that owns env-spec metadata and delegates tools."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .identity import env_spec_fingerprint
from .protocol import EnvironmentBackend


class EnvironmentFacade:
    """Holds python / requirements / env vars; delegates lifecycle to a backend.

    This is the target shape for ``asv.environment.Environment`` after a
    full migration. The spike keeps the legacy class for production paths.
    """

    def __init__(
        self,
        backend: EnvironmentBackend,
        python: str,
        requirements: Mapping[str, str],
        tagged_env_vars: Mapping[str, str],
    ):
        self._backend = backend
        self.python = python
        self.requirements = dict(requirements)
        self.tagged_env_vars = dict(tagged_env_vars)

    @property
    def tool_name(self) -> str:
        return self._backend.tool_name

    def fingerprint(self, *, build: bool = False) -> str:
        return env_spec_fingerprint(
            self.tool_name,
            self.python,
            self.requirements,
            self.tagged_env_vars,
            build=build,
        )

    def create(self) -> None:
        self._backend.create()

    def install_project(
        self, package: str, install_commands: Sequence[str], env_vars: Mapping[str, str]
    ) -> None:
        self._backend.install_project(package, install_commands, env_vars)

    def run(
        self,
        args: Sequence[str],
        *,
        env_vars: Optional[Mapping[str, str]] = None,
        cwd: Optional[str] = None,
    ):
        return self._backend.run(args, env_vars=env_vars, cwd=cwd)

    def python_executable(self) -> str:
        return self._backend.python_executable()
