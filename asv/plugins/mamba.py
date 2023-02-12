# Licensed under a 3-clause BSD style license - see LICENSE.rst
import re
import os
import tempfile
import contextlib

from .. import environment, util
from ..console import log

WIN = (os.name == "nt")


def _find_mamba():
    """
    Find the mamba executable robustly across mamba versions.

    Returns
    -------
    mamba : str
        Path to the mamba executable.

    Raises
    ------
    IOError
        If the executable cannot be found in either the MAMBA_EXE environment
        variable or in the PATH.

    Notes
    -----
    In POSIX platforms in mamba >= 4.4, mamba can be set up as a bash function
    rather than an executable. (This is to enable the syntax
    ``mamba activate env-name``.) In this case, the environment variable
    ``MAMBA_EXE`` contains the path to the mamba executable. In other cases,
    we use standard search for the appropriate name in the PATH.

    See https://github.com/airspeed-velocity/asv/issues/645 for more details.
    """
    if 'MAMBA_EXE' in os.environ:
        mamba = os.environ['MAMBA_EXE']
    else:
        mamba = util.which('mamba')
    return mamba


class Mamba(environment.Environment):
    """
    Manage an environment using mamba.

    Dependencies are installed using ``mamba``.  The benchmarked
    project is installed using ``pip`` (since ``mamba`` doesn't have a
    method to install from an arbitrary ``setup.py``).
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
        self._python = python
        self._requirements = requirements
        self._mamba_channels = conf.conda_channels
        self._mamba_environment_file = conf.conda_environment_file
        super(Mamba, self).__init__(conf,
                                    python,
                                    requirements,
                                    tagged_env_vars)

    @classmethod
    def matches(cls, python):
        # Calling mamba can take a long time, so remember the result
        if python not in cls._matches_cache:
            cls._matches_cache[python] = cls._matches(python)
        return cls._matches_cache[python]

    @classmethod
    def _matches(cls, python):
        if not re.match(r'^[0-9].*$', python):
            # The python name should be a version number
            return False

        try:
            mamba = _find_mamba()
        except IOError:
            return False
        else:
            # This directory never gets created, since we're just
            # doing a dry run below. All it needs to be is something
            # that doesn't already exist.
            path = os.path.join(tempfile.gettempdir(), 'check')

            # Check that the version number is valid
            try:
                util.check_call([
                    mamba,
                    'create',
                    '--yes',
                    '-p',
                    path,
                    'python={0}'.format(python),
                    '--dry-run'], display_error=False, dots=False)
            except util.ProcessError:
                return False
            else:
                return True

    def _setup(self):
        log.info("Creating mamba environment for {0}".format(self.name))

        mamba_args, pip_args = self._get_requirements()
        env = dict(os.environ)
        env.update(self.build_env_vars)

        if not self._mamba_environment_file:
            # The user-provided env file is assumed to set the python version
            mamba_args = ['python={0}'.format(self._python), 'wheel', 'pip'] + mamba_args

        # Create a temporary environment.yml file
        # and use that to generate the env for benchmarking.
        env_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yml")
        try:
            env_file.write('name: {0}\n'
                           'channels:\n'.format(self.name))
            env_file.writelines(('   - %s\n' % ch for ch in self._mamba_channels))
            env_file.write('dependencies:\n')

            # categorize & write dependencies based on pip vs. mamba
            env_file.writelines(('   - %s\n' % s for s in mamba_args))
            if pip_args:
                # and now specify the packages that are to be installed in
                # the pip subsection
                env_file.write('   - pip:\n')
                env_file.writelines(('     - %s\n' % s for s in pip_args))

            env_file.close()

            try:
                env_file_name = self._mamba_environment_file or env_file.name
                self._run_mamba(['env', 'create', '-f', env_file_name,
                                 '-p', self._path, '--force'],
                                env=env)

                if self._mamba_environment_file and (mamba_args or pip_args):
                    # Add extra packages
                    env_file_name = env_file.name
                    self._run_mamba(['env', 'update', '-f', env_file_name,
                                     '-p', self._path],
                                    env=env)
            except Exception:
                if env_file_name != env_file.name:
                    log.info("mamba env create/update failed: "
                             "in {} with file {}".format(self._path, env_file_name))
                elif os.path.isfile(env_file_name):
                    with open(env_file_name, 'r') as f:
                        text = f.read()
                    log.info("mamba env create/update failed: "
                             "in {} with:\n{}".format(self._path, text))
                raise
        finally:
            os.unlink(env_file.name)

    def _get_requirements(self):
        if self._requirements:
            # retrieve and return all mamba / pip dependencies
            mamba_args = []
            pip_args = []

            for key, val in self._requirements.items():
                if key.startswith('pip+'):
                    if val:
                        pip_args.append("{0}=={1}".format(key[4:], val))
                    else:
                        pip_args.append(key[4:])
                else:
                    if val:
                        mamba_args.append("{0}={1}".format(key, val))
                    else:
                        mamba_args.append(key)

            return mamba_args, pip_args
        else:
            return [], []

    def _run_mamba(self, args, env=None):
        """
        Run mamba command outside the environment.
        """
        try:
            mamba = _find_mamba()
        except IOError as e:
            raise util.UserError(str(e))

        return util.check_output([mamba] + args, env=env)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self.run_executable('python', args, **kwargs)

    def run_executable(self, executable, args, **kwargs):
        # Special-case running mamba, for user-provided commands
        if executable == "mamba":
            executable = _find_mamba()

        return super(Mamba, self).run_executable(executable, args, **kwargs)
