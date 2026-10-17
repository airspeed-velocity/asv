# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Tool-specific environment backend protocol.

Backends implement create / install / run / identity hooks only.
Matrix expansion and conf parsing stay outside this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Optional, Sequence


class EnvironmentBackend(ABC):
    """Backend for a single environment *tool* (virtualenv, conda, uv, ...).

    One backend instance is bound to a concrete env directory and tool
    configuration. Orchestration (``Environment`` facade) owns python
    version, requirement dicts, and tagged env vars.
    """

    tool_name: str = "abstract"

    @abstractmethod
    def create(self) -> None:
        """Create an empty environment at the backend path."""

    @abstractmethod
    def install_project(
        self,
        package: str,
        install_commands: Sequence[str],
        env_vars: Mapping[str, str],
    ) -> None:
        """Install the project under test into the environment."""

    @abstractmethod
    def run(
        self,
        args: Sequence[str],
        *,
        env_vars: Optional[Mapping[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Any:
        """Run a command inside the environment (return code or output)."""

    @abstractmethod
    def python_executable(self) -> str:
        """Absolute path to the environment Python interpreter."""

    def identity_payload(
        self,
        python: str,
        requirements: Mapping[str, str],
        tagged_env_vars: Mapping[str, str],
    ) -> Dict[str, Any]:
        """Optional structured identity for caching; default is tool name only."""
        return {"tool": self.tool_name, "python": python}
