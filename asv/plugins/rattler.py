import os
import asyncio
from pathlib import Path

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

from rattler import solve, install, VirtualPackage

from .. import environment, util
from ..console import log


class Rattler(environment.Environment):
    """
    Manage an environment using py-rattler.

    Dependencies are installed using py-rattler. The benchmarked
    project is installed using the build command specified.
    """

    tool_name = "rattler"

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
        self._python = python
        self._requirements = requirements
        self._channels = conf.conda_channels
        self._environment_file = None

        if conf.conda_environment_file == "IGNORE":
            log.debug(
                "Skipping environment file due to conda_environment_file set to IGNORE"
            )
            self._environment_file = None
        elif not conf.conda_environment_file:
            if (Path("environment.yml")).exists():
                log.debug("Using environment.yml")
                self._environment_file = "environment.yml"
        else:
            if (Path(conf.conda_environment_file)).exists():
                log.debug(f"Using {conf.conda_environment_file}")
                self._environment_file = conf.conda_environment_file
            else:
                log.debug(
                    f"Environment file {conf.conda_environment_file} not found, ignoring"
                )

        super(Rattler, self).__init__(conf, python, requirements, tagged_env_vars)
        # Rattler configuration things
        self._pkg_cache = f"{self._env_dir}/pkgs"

        # TODO(haozeke): Provide channel priority, see mamba

    def _setup(self):
        asyncio.run(self._async_setup())

    async def _async_setup(self):
        log.info(f"Creating environment for {self.name}")

        _args, pip_args = self._get_requirements()
        _pkgs = ["python", "wheel", "pip"]  # baseline, overwritten by env file
        env = dict(os.environ)
        env.update(self.build_env_vars)
        if self._environment_file:
            # For named environments
            env_file_name = self._environment_file
            env_data = load(Path(env_file_name).open(), Loader=Loader)
            _pkgs = [x for x in env_data.get("dependencies", []) if isinstance(x, str)]
            self._channels += [
                x for x in env_data.get("channels", []) if isinstance(x, str)
            ]
            self._channels = list(dict.fromkeys(self._channels).keys())
            # Handle possible pip keys
            pip_maybe = [
                x for x in env_data.get("dependencies", []) if isinstance(x, dict)
            ]
            if len(pip_maybe) == 1:
                try:
                    pip_args += pip_maybe[0]["pip"]
                except KeyError:
                    raise KeyError("Only pip is supported as a secondary key")
        _pkgs += _args
        _pkgs = [util.replace_python_version(pkg, self._python) for pkg in _pkgs]
        solved_records = await solve(
            # Channels to use for solving
            channels=self._channels,
            # The specs to solve for
            specs=_pkgs,
            # Virtual packages define the specifications of the environment
            virtual_packages=VirtualPackage.detect(),
        )
        await install(records=solved_records, target_prefix=self._path)
        if pip_args:
            for declaration in pip_args:
                parsed_declaration = util.ParsedPipDeclaration(declaration)
                pip_call = util.construct_pip_call(self._run_pip, parsed_declaration)
                pip_call()

    def _get_requirements(self):
        _args = []
        pip_args = []

        for key, val in {**self._requirements, **self._base_requirements}.items():
            if key.startswith("pip+"):
                pip_args.append(f"{key[4:]} {val}")
            else:
                if val:
                    _args.append(f"{key}={val}")
                else:
                    _args.append(key)

        return _args, pip_args

    def run_executable(self, executable, args, **kwargs):
        return super(Rattler, self).run_executable(executable, args, **kwargs)

    def run(self, args, **kwargs):
        log.debug(f"Running '{' '.join(args)}' in {self.name}")
        return self.run_executable("python", args, **kwargs)

    def _run_pip(self, args, **kwargs):
        # Run pip via python -m pip, so that it works on Windows when
        # upgrading pip itself, and avoids shebang length limit on Linux
        return self.run_executable("python", ["-mpip"] + list(args), **kwargs)
