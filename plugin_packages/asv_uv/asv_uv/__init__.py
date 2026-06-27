# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""ASV uv-oriented environment plugin.

PyPI ``uv`` is primarily a **CLI** distribution; there is no stable public
Python API for ``uv venv`` comparable to py-rattler/libmamba. This backend
therefore:

1. Creates envs with the **stdlib ``venv`` API** (in-process).
2. Installs requirements with **``python -m pip``** inside that env (interpreter API).

If a future ``uv`` library API appears, prefer it here over subprocess to ``uv``.
The ``uv`` binary is **not** required.
"""

from __future__ import annotations

import os
import re
import venv

from asv import environment, util
from asv.console import log

WIN = os.name == "nt"


class Uv(environment.Environment):
    """venv + pip API backend registered as environment_type ``uv``."""

    tool_name = "uv"

    def __init__(self, conf, python, requirements, tagged_env_vars):
        self._python = python
        self._requirements = requirements
        super().__init__(conf, python, requirements, tagged_env_vars)
        # Prefer host interpreter matching version when possible
        try:
            from asv.plugins.virtualenv import Virtualenv

            self._host_python = Virtualenv._find_python(python)
        except Exception:
            self._host_python = None
        if self._host_python is None:
            raise environment.EnvironmentUnavailable(
                f"No host Python executable for {python} (needed to seed venv API)"
            )

    @classmethod
    def matches(cls, python):
        if not (re.match(r"^[0-9].*$", python) or re.match(r"^pypy[0-9.]*$", python)):
            return False
        try:
            from asv.plugins.virtualenv import Virtualenv

            return Virtualenv._find_python(python) is not None
        except Exception:
            return False

    def _setup(self):
        log.info(f"Creating venv (stdlib API) for {self.name} [uv-oriented plugin]")
        builder = venv.EnvBuilder(with_pip=True, clear=False)
        # EnvBuilder uses current interpreter; document limitation vs multi-version.
        # For multi-version, users need host pythons on PATH (same as virtualenv plugin).
        builder.create(self._path)
        self._install_requirements()

    def _install_requirements(self):
        pip_args = ["install", "-v", "wheel", "pip>=8"]
        env = dict(os.environ)
        env.update(self.build_env_vars)
        self._run_pip(pip_args, env=env)
        for key, val in {**self._requirements, **self._base_requirements}.items():
            if key.startswith("pip+"):
                declaration = f"{key[4:]} {val}" if val else key[4:]
            else:
                declaration = f"{key} {val}" if val else key
            parsed = util.ParsedPipDeclaration(declaration)
            util.construct_pip_call(self._run_pip, parsed)()

    def _run_pip(self, args, **kwargs):
        return self.run_executable("python", ["-m", "pip"] + list(args), **kwargs)

    def run(self, args, **kwargs):
        return self.run_executable("python", args, **kwargs)
