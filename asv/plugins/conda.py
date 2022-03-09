# Licensed under a 3-clause BSD style license - see LICENSE.rst
import re
import os
import tempfile
import contextlib

from .. import environment, util
from ..console import log

WIN = (os.name == "nt")


# Conda (as of version 4.7.5) is not safe to run in parallel.
# See https://github.com/conda/conda/issues/8870
# Hence, serialize the calls to it.

util.new_multiprocessing_lock("conda_lock")


def _conda_lock():
    # function; for easier monkeypatching
    return util.get_multiprocessing_lock("conda_lock")


@contextlib.contextmanager
def _dummy_lock():
    yield


def _find_conda():
    """
    Find the conda executable robustly across conda versions.

    Returns
    -------
    conda : str
        Path to the conda executable.

    Raises
    ------
    IOError
        If the executable cannot be found in either the CONDA_EXE environment
        variable or in the PATH.

    Notes
    -----
    In POSIX platforms in conda >= 4.4, conda can be set up as a bash function
    rather than an executable. (This is to enable the syntax
    ``conda activate env-name``.) In this case, the environment variable
    ``CONDA_EXE`` contains the path to the conda executable. In other cases,
    we use standard search for the appropriate name in the PATH.

    See https://github.com/airspeed-velocity/asv/issues/645 for more details.
    """
    if 'CONDA_EXE' in os.environ:
        conda = os.environ['CONDA_EXE']
    else:
        conda = util.which('conda')
    return conda


class Conda(environment.Environment):
    """
    Manage an environment using conda.

    Dependencies are installed using ``conda``.  The benchmarked
    project is installed using ``pip`` (since ``conda`` doesn't have a
    method to install from an arbitrary ``setup.py``).
    """
    tool_name = "conda"
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
        self._conda_channels = conf.conda_channels
        self._conda_environment_file = conf.conda_environment_file
        super(Conda, self).__init__(conf,
                                    python,
                                    requirements,
                                    tagged_env_vars)

    @classmethod
    def matches(cls, python):
        # Calling conda can take a long time, so remember the result
        if python not in cls._matches_cache:
            cls._matches_cache[python] = cls._matches(python)
        return cls._matches_cache[python]

    @classmethod
    def _matches(cls, python):
        if not re.match(r'^[0-9].*$', python):
            # The python name should be a version number
            return False

        try:
            conda = _find_conda()
        except IOError:
            return False
        else:
            # This directory never gets created, since we're just
            # doing a dry run below.  All it needs to be is something
            # that doesn't already exist.
            path = os.path.join(tempfile.gettempdir(), 'check')

            # Check that the version number is valid
            try:
                with _conda_lock():
                    util.check_call([
                        conda,
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
        log.info("Creating conda environment for {0}".format(self.name))

        conda_args, pip_args = self._get_requirements()
        env = dict(os.environ)
        env.update(self.build_env_vars)

        if not self._conda_environment_file:
            # The user-provided env file is assumed to set the python version
            conda_args = ['python={0}'.format(self._python), 'wheel', 'pip'] + conda_args

        # Create a temporary environment.yml file
        # and use that to generate the env for benchmarking.
        env_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".yml")
        try:
            env_file.write('name: {0}\n'
                           'channels:\n'.format(self.name))
            env_file.writelines(('   - %s\n' % ch for ch in self._conda_channels))
            env_file.write('dependencies:\n')

            # categorize & write dependencies based on pip vs. conda
            env_file.writelines(('   - %s\n' % s for s in conda_args))
            if pip_args:
                # and now specify the packages that are to be installed in
                # the pip subsection
                env_file.write('   - pip:\n')
                env_file.writelines(('     - %s\n' % s for s in pip_args))

            env_file.close()

            try:
                env_file_name = self._conda_environment_file or env_file.name
                self._run_conda(['env', 'create', '-f', env_file_name,
                                 '-p', self._path, '--force'],
                                env=env)

                if self._conda_environment_file and (conda_args or pip_args):
                    # Add extra packages
                    env_file_name = env_file.name
                    self._run_conda(['env', 'update', '-f', env_file_name,
                                     '-p', self._path],
                                    env=env)
            except Exception:
                if env_file_name != env_file.name:
                    log.info("conda env create/update failed: "
                             "in {} with file {}".format(self._path, env_file_name))
                elif os.path.isfile(env_file_name):
                    with open(env_file_name, 'r') as f:
                        text = f.read()
                    log.info("conda env create/update failed: "
                             "in {} with:\n{}".format(self._path, text))
                raise
        finally:
            os.unlink(env_file.name)

    def _get_requirements(self):
        if self._requirements:
            # retrieve and return all conda / pip dependencies
            conda_args = []
            pip_args = []

            for key, val in self._requirements.items():
                if key.startswith('pip+'):
                    if val:
                        pip_args.append("{0}=={1}".format(key[4:], val))
                    else:
                        pip_args.append(key[4:])
                else:
                    if val:
                        conda_args.append("{0}={1}".format(key, val))
                    else:
                        conda_args.append(key)

            return conda_args, pip_args
        else:
            return [], []

    def _run_conda(self, args, env=None):
        """
        Run conda command outside the environment.
        """
        try:
            conda = _find_conda()
        except IOError as e:
            raise util.UserError(str(e))

        with _conda_lock():
            return util.check_output([conda] + args, env=env)

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return self.run_executable('python', args, **kwargs)

    def run_executable(self, executable, args, **kwargs):
        # Special-case running conda, for user-provided commands
        if executable == "conda":
            executable = _find_conda()
            lock = _conda_lock
        else:
            lock = _dummy_lock

        # Conda doesn't guarantee that user site directories are excluded
        kwargs["env"] = dict(kwargs.pop("env", os.environ),
                             PYTHONNOUSERSITE=str("True"))

        with lock():
            return super(Conda, self).run_executable(executable, args, **kwargs)
