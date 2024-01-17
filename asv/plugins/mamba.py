# Licensed under a 3-clause BSD style license - see LICENSE.rst
# ONLY works on newer python versions
import os
import re
from pathlib import Path

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

try:
    from mamba.api import MambaSolver
    import libmambapy
    _HAS_LIBMAMBAPY = True
except ImportError:
    _HAS_LIBMAMBAPY = False


from .. import environment, util
from ..console import log

WIN = os.name == "nt"

# Like Conda, Mamba also needs to be serialized
util.new_multiprocessing_lock("mamba_lock")


def _mamba_lock():
    # function; for easier monkeypatching
    return util.get_multiprocessing_lock("mamba_lock")


class Mamba(environment.Environment):
    """
    Manage an environment using mamba.

    Dependencies are installed using ``mamba``.  The benchmarked
    project is installed using ``pip``.
    """

    tool_name = "mamba"
    _matches_cache = {}

    def __init__(self, conf, python, requirements, tagged_env_vars):
        """
        Parameters
        ----------
        conf : Config instance

        python : str
            Version of Python.  Must be of the form "MAJOR.MINOR".

        requirements : dict
            Dictionary mapping a PyPI package name to a version
            identifier string.
        """
        if not _HAS_LIBMAMBAPY:
            raise ImportError("Failed to import 'libmambapy' Python module.")
        self._python = python
        self._requirements = requirements
        self._mamba_channels = conf.conda_channels
        self._mamba_environment_file = None
        if "conda-forge" not in conf.conda_channels:
            self._mamba_channels += ["conda-forge"]

        if conf.conda_environment_file == "IGNORE":
            log.debug("Skipping environment file due to conda_environment_file set to IGNORE")
            self._mamba_environment_file = None
        elif not conf.conda_environment_file:
            if (Path("environment.yml")).exists():
                log.debug("Using environment.yml")
                self._mamba_environment_file = "environment.yml"
        else:
            if (Path(conf.conda_environment_file)).exists():
                log.debug(f"Using {conf.conda_environment_file}")
                self._mamba_environment_file = conf.conda_environment_file
            else:
                log.debug(f"Environment file {conf.conda_environment_file} not found, ignoring")

        super(Mamba, self).__init__(conf, python, requirements, tagged_env_vars)
        self.context = libmambapy.Context()
        self.context.target_prefix = self._path

    @classmethod
    def matches(cls, python):
        # Calling mamba can take a long time, so remember the result
        if python not in cls._matches_cache:
            cls._matches_cache[python] = cls._matches(python)
        return cls._matches_cache[python]

    @classmethod
    def _matches(cls, python):
        if not re.match(r'^[0-9].*$', python):
            return False
        else:
            if os.getenv("CONDA_EXE"):
                mamba_path = str(Path(os.getenv("CONDA_EXE")).parent / "mamba")
            else:
                return False
            try:
                return util.search_channels(mamba_path, "python", python)
            except util.ProcessError:
                return False

    def _setup(self):
        log.info(f"Creating mamba environment for {self.name}")

        mamba_args, pip_args = self._get_requirements()
        if len(pip_args) > 0:
            self.context.add_pip_as_python_dependency = True
        env = dict(os.environ)
        env.update(self.build_env_vars)
        Path(f"{self._path}/conda-meta").mkdir(parents=True, exist_ok=True)
        if not self._mamba_environment_file:
            # Construct payload, env file sets python version
            mamba_pkgs = [f"python={self._python}", "wheel", "pip"] + mamba_args
        else:
            # For named environments
            env_file_name = self._mamba_environment_file
            env_data = load(Path(env_file_name).open(), Loader=Loader)
            mamba_pkgs = [x for x in env_data.get("dependencies", []) if isinstance(x, str)]
            self._mamba_channels += [x for x in env_data.get("channels", []) if isinstance(x, str)]
            self._mamba_channels = list(dict.fromkeys(self._mamba_channels).keys())
            # Handle possible pip keys
            pip_maybe = [x for x in env_data.get("dependencies", []) if isinstance(x, dict)]
            if len(pip_maybe) == 1:
                try:
                    pip_args += pip_maybe[0]["pip"]
                except KeyError:
                    raise KeyError("Only pip is supported as a secondary key")
        solver = MambaSolver(
            self._mamba_channels, None, self.context  # or target_platform
        )
        with _mamba_lock():
            transaction = solver.solve(mamba_pkgs)
            transaction.execute(libmambapy.PrefixData(self._path))
            if pip_args:
                for declaration in pip_args:
                    parsed_declaration = util.ParsedPipDeclaration(declaration)
                    pip_call = util.construct_pip_call(self._run_pip, parsed_declaration)
                    pip_call()

    def _get_requirements(self):
        mamba_args = []
        pip_args = []

        for key, val in {**self._requirements,
                         **self._base_requirements}.items():
            if key.startswith("pip+"):
                pip_args.append(f"{key[4:]} {val}")
            else:
                if val:
                    mamba_args.append(f"{key}={val}")
                else:
                    mamba_args.append(key)

        return mamba_args, pip_args

    def run_executable(self, executable, args, **kwargs):
        return super(Mamba, self).run_executable(executable, args, **kwargs)

    def run(self, args, **kwargs):
        log.debug(f"Running '{' '.join(args)}' in {self.name}")
        return self.run_executable("python", args, **kwargs)

    def _run_pip(self, args, **kwargs):
        # Run pip via python -m pip, so that it works on Windows when
        # upgrading pip itself, and avoids shebang length limit on Linux
        return self.run_executable("python", ["-mpip"] + list(args), **kwargs)
