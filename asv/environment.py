# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Manages an environment -- a combination of a version of Python and set
of dependencies.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import hashlib
import os
import re
import shutil
import sys
import itertools
import subprocess

import six

from .console import log
from . import util
from . import wheel_cache


WIN = (os.name == "nt")


def iter_requirement_matrix(environment_type, pythons, conf, explicit_selection=False):
    """
    Iterate through all combinations of the given requirement
    matrix and python versions.
    """

    env_classes = {}

    def get_env_type(python):
        env_type = env_classes.get(python)
        if env_type is None:
            cls = get_environment_class(conf, python)
            env_type = cls.tool_name
            env_classes[python] = env_type
        return env_type

    platform_keys = {
        'environment_type': environment_type,
        'sys_platform': sys.platform
    }

    # Parse input
    keys = sorted(conf.matrix.keys())
    values = [conf.matrix[key] for key in keys]
    values = [value if isinstance(value, list) else [value]
              for value in values]
    values = [[''] if value == [] else value
              for value in values]

    # Process excludes
    for python in pythons:
        empty_matrix = True

        # Cartesian product of everything
        all_keys = ['python'] + keys
        all_combinations = itertools.product([python], *values)

        for combination in all_combinations:
            target = dict(zip(all_keys, combination))
            target.update(platform_keys)

            if not environment_type:
                try:
                    target['environment_type'] = get_env_type(target['python'])
                except EnvironmentUnavailable as err:
                    log.warn(str(err))
                    continue

            for rule in conf.exclude:
                # check if all fields in the rule match
                if match_rule(target, rule):
                    # rule matched
                    break
            else:
                # not excluded
                empty_matrix = False
                yield dict(item for item in zip(all_keys, combination)
                           if item[1] is not None)

        # If the user explicitly selected environment/python, yield it
        # even if matrix contains no packages to be installed
        if empty_matrix and explicit_selection:
            yield dict(python=python)

    # Process includes, unless explicit selection
    if explicit_selection:
        return

    for include in conf.include:
        if 'python' not in include:
            raise util.UserError("include rule '{0}' does not specify Python version".format(include))

        include = dict(include)

        # Platform keys in include statement act as matching rules
        target = dict(platform_keys)

        if not environment_type:
            try:
                target['environment_type'] = get_env_type(include['python'])
            except EnvironmentUnavailable as err:
                log.warn(str(err))
                continue

        rule = {}

        for key in platform_keys.keys():
            if key in include:
                rule[key] = include.pop(key)

        if match_rule(target, rule):
            # Prune empty keys
            for key in list(include.keys()):
                if include[key] is None:
                    include.pop(key)

            yield include


def match_rule(target, rule):
    """
    Match rule to a target.

    Parameters
    ----------
    target : dict
        Dictionary containing [(key, value), ...].
        Keys must be str, values must be str or None.
    rule : dict
        Dictionary containing [(key, match), ...], to be matched
        to *target*. Match can be str specifying a regexp that must
        match target[key], or None. None matches either None
        or a missing key in *target*. If match is not None,
        and the key is missing in *target*, the rule does not match.

    Returns
    -------
    matched : bool
        Whether the rule matched. The rule matches if
        all keys match.

    """
    for key, value in rule.items():
        if value is None:
            if key in target and target[key] is not None:
                return False
        elif key not in target or target[key] is None:
            return False
        else:
            w = str(target[key])
            m = re.match(str(value), w)
            if m is None or m.end() != len(w):
                return False

    # rule matched
    return True


def get_env_name(tool_name, python, requirements):
    """
    Get a name to uniquely identify an environment.
    """
    if tool_name:
        name = [tool_name]
    else:
        # Backward compatibility vs. result file names
        name = []

    name.append("py{0}".format(python))
    reqs = list(six.iteritems(requirements))
    reqs.sort()
    for key, val in reqs:
        if val:
            name.append(''.join([key, val]))
        else:
            name.append(key)
    return util.sanitize_filename('-'.join(name))


def get_environments(conf, env_specifiers):
    """
    Iterator returning `Environment` objects for all of the
    permutations of the given versions of Python and a matrix of
    requirements.

    Parameters
    ----------
    conf : dict
        asv configuration object
    env_specifiers : list of str
        List of environment specifiers, in the format
        'env_name:python_spec'. If *env_name* is empty, autodetect
        it. If *python_spec* is missing, use those listed in the
        configuration file. Alternatively, can be the name given
        by *Environment.name* if the environment is in the matrix.

    """

    if not env_specifiers:
        all_environments = ()
        env_specifiers = [conf.environment_type]
        if not conf.environment_type:
            log.warn(
                "No `environment_type` specified in asv.conf.json. "
                "This will be required in the future.")
    else:
        all_environments = list(get_environments(conf, None))

    for env_spec in env_specifiers:
        env_name_found = False
        for env in all_environments:
            if env_spec == env.name:
                env_name_found = True
                yield env
                break
        if env_name_found:
            continue

        explicit_selection = False

        if env_spec and ':' in env_spec:
            env_type, python_spec = env_spec.split(':', 1)
            pythons = [python_spec]
            explicit_selection = True
        else:
            env_type = env_spec
            if env_type == "existing":
                explicit_selection = True
                pythons = ["same"]
            else:
                pythons = conf.pythons

        if env_type != "existing":
            requirements_iter = iter_requirement_matrix(env_type, pythons, conf,
                                                        explicit_selection)
        else:
            # Ignore requirement matrix
            requirements_iter = [dict(python=python) for python in pythons]

        for requirements in requirements_iter:
            python = requirements.pop('python')

            try:
                if env_type:
                    cls = get_environment_class_by_name(env_type)
                else:
                    cls = get_environment_class(conf, python)

                yield cls(conf, python, requirements)
            except EnvironmentUnavailable as err:
                log.warn(str(err))


def get_environment_class(conf, python):
    """
    Get a matching environment type class.

    Parameters
    ----------
    conf : dict
        asv configuration object

    python : str
        Python version specifier.  Acceptable values depend on the
        Environment plugins installed but generally are:

        - 'X.Y': A Python version, in which case conda or virtualenv
          will be used to create a new environment.

        - 'python' or '/usr/bin/python': Search for the given
          executable on the search PATH, and use that.  It is assumed
          that all dependencies and the benchmarked project itself are
          already installed.
    """
    if python == 'same':
        return ExistingEnvironment

    # Try the subclasses in reverse order so custom plugins come first
    classes = list(util.iter_subclasses(Environment))[::-1]

    if conf.environment_type:
        cls = get_environment_class_by_name(conf.environment_type)
        classes.remove(cls)
        classes.insert(0, cls)

    for cls in classes:
        if cls.matches(python):
            return cls
    raise EnvironmentUnavailable(
        "No way to create environment for python='{0}'".format(python))


def get_environment_class_by_name(environment_type):
    """
    Find the environment class with the given name.
    """
    for cls in util.iter_subclasses(Environment):
        if cls.tool_name == environment_type:
            return cls
    raise EnvironmentUnavailable(
        "Unknown environment type '{0}'".format(environment_type))


def is_existing_only(environments):
    """
    Check if the list of environments only contains ExistingEnvironment
    """
    return all(isinstance(env, ExistingEnvironment) for env in environments)


class EnvironmentUnavailable(BaseException):
    pass


class Environment(object):
    """
    Manage a single environment -- a combination of a particular
    version of Python and a set of dependencies for the benchmarked
    project.
    """
    tool_name = None

    def __init__(self, conf, python, requirements):
        """
        Get an environment for a given requirement matrix and
        Python version specifier.

        Parameters
        ----------
        conf : dict
            asv configuration object

        python : str
            A Python version specifier.  This is the same as passed to
            the `matches` method, and its exact meaning depends on the
            environment.

        requirements : dict (str -> str)
            Mapping from package names to versions

        Raises
        ------
        EnvironmentUnavailable
            The environment for the given combination is not available.

        """
        self._env_dir = conf.env_dir
        self._repo_subdir = conf.repo_subdir
        self._install_timeout = conf.install_timeout  # GH391
        self._path = os.path.abspath(os.path.join(
            self._env_dir, self.hashname))

        self._is_setup = False

        self._cache = wheel_cache.WheelCache(conf, self._path)
        self._build_root = os.path.abspath(os.path.join(self._path, 'project'))

        self._env_vars = {}
        self._env_vars['ASV'] = 'true'
        self._env_vars['ASV_PROJECT'] = conf.project
        self._env_vars['ASV_ENV_NAME'] = self.name
        self._env_vars['ASV_ENV_PATH'] = self._path
        self._env_vars['ASV_ENV_TYPE'] = self.tool_name

    @classmethod
    def matches(self, python):
        """
        Returns `True` if this environment subclass can handle the
        given Python specifier.
        """
        return False

    @property
    def name(self):
        """
        Get a name to uniquely identify this environment.
        """
        return get_env_name(self.tool_name, self._python, self._requirements)

    @property
    def hashname(self):
        """
        Get a hash to uniquely identify this environment.
        """
        return hashlib.md5(self.name.encode('utf-8')).hexdigest()

    @property
    def requirements(self):
        return self._requirements

    @property
    def python(self):
        return self._python

    def check_presence(self):
        """
        Check whether the environment already exists.
        """
        if not os.path.isdir(self._env_dir):
            return False

        try:
            info = self.load_info_file(self._path)
        except (util.UserError, IOError):
            return False

        expected_info = {
            'tool_name': self.tool_name,
            'python': self._python,
            'requirements': self._requirements
        }

        if info != expected_info:
            return False

        for executable in ['pip', 'python']:
            try:
                self.find_executable(executable)
            except IOError:
                return False

        try:
            self.run_executable('python', ['-c', 'pass'])
        except (subprocess.CalledProcessError, OSError):
            return False

        return True

    def create(self):
        """
        Create the environment on disk.  If it doesn't exist, it is
        created.  Then, all of the requirements are installed into it.
        """
        if self._is_setup:
            return

        if not self.check_presence():
            if os.path.exists(self._path):
                util.long_path_rmtree(self._path)

            if not os.path.exists(self._env_dir):
                try:
                    os.makedirs(self._env_dir)
                except OSError:
                    # Environment.create may be called in parallel for
                    # environments with different self._path, but same
                    # self._env_dir. This causes a race condition for
                    # the above makedirs() call --- but not for the
                    # rest of the processing. Therefore, we will just
                    # ignore the error here, as things will fail at a
                    # later stage if there is really was a problem.
                    pass

            try:
                self._setup()
            except:
                log.error("Failure creating environment for {0}".format(self.name))
                if os.path.exists(self._path):
                    util.long_path_rmtree(self._path)
                raise

        self.save_info_file(self._path)

        self._is_setup = True

    def _setup(self):
        """
        Implementation for setting up the environment.
        """
        raise NotImplementedError()

    def install(self, package):
        """
        Install a package into the environment.
        """
        raise NotImplementedError()

    def uninstall(self, package):
        """
        Uninstall a package into the environment.
        """
        raise NotImplementedError()

    def run(self, args, **kwargs):
        """
        Start up the environment's python executable with the given
        args.
        """
        raise NotImplementedError()

    def checkout_project(self, repo, commit_hash):
        """
        Check out the working tree of the project at given commit hash
        """
        self._set_commit_hash(commit_hash)
        repo.checkout(self._build_root, commit_hash)

    def build_project(self, repo, commit_hash):
        self.checkout_project(repo, commit_hash)
        log.info("Building {0} for {1}".format(commit_hash[:8], self.name))
        if self._repo_subdir:
            build_dir = os.path.join(self._build_root, self._repo_subdir)
        else:
            build_dir = self._build_root
        self.run(['setup.py', 'build'], cwd=build_dir)
        return build_dir

    def install_project(self, conf, repo, commit_hash):
        """
        Install the benchmarked project into the environment.
        Uninstalls any installed copy of the project first.
        """
        self.uninstall(conf.project)

        self._set_commit_hash(commit_hash)

        build_root = self._cache.build_project_cached(
            self, conf, repo, commit_hash)

        if build_root is None:
            build_root = self.build_project(repo, commit_hash)

        self.install(build_root)

    def can_install_project(self):
        """
        Return `True` if specific revisions of the benchmarked project
        can be installed into this environment.
        """
        return True

    def find_executable(self, executable):
        """
        Find an executable (eg. python, pip) in the environment.

        If not found, raises IOError
        """

        # Assume standard virtualenv/Conda layout
        if WIN:
            paths = [self._path,
                     os.path.join(self._path, 'Scripts'),
                     os.path.join(self._path, 'bin')]
        else:
            paths = [os.path.join(self._path, 'bin')]

        return util.which(executable, paths)

    def run_executable(self, executable, args, **kwargs):
        """
        Run a given executable (eg. python, pip) in the environment.
        """
        env = kwargs.pop("env", os.environ).copy()
        env.update(self._env_vars)

        # Insert bin dirs to PATH
        if "PATH" in env:
            paths = env["PATH"].split(os.pathsep)
        else:
            paths = []

        if WIN:
            subpaths = ['Library\\mingw-w64\\bin',
                        'Library\\bin',
                        'Library\\usr\\bin',
                        'Scripts']
            for sub in subpaths[::-1]:
                paths.insert(0, os.path.join(self._path, sub))
            paths.insert(0, self._path)
        else:
            paths.insert(0, os.path.join(self._path, "bin"))

        # When running pip, we need to set PIP_USER to false, as --user (which
        # may have been set from a pip config file) is incompatible with
        # virtualenvs.
        kwargs["env"] = dict(env,
                             PIP_USER=str("false"),
                             PATH=str(os.pathsep.join(paths)))
        exe = self.find_executable(executable)
        return util.check_output([exe] + args, **kwargs)

    def load_info_file(self, path):
        path = os.path.join(path, 'asv-env-info.json')
        return util.load_json(path)

    def save_info_file(self, path):
        """
        Save a file with information about the environment into
        directory `path`.
        """
        path = os.path.join(path, 'asv-env-info.json')
        content = {
            'tool_name': self.tool_name,
            'python': self._python,
            'requirements': self._requirements
        }
        util.write_json(path, content)

    def _set_commit_hash(self, commit_hash):
        self._env_vars['ASV_COMMIT'] = commit_hash


class ExistingEnvironment(Environment):
    tool_name = "existing"

    def __init__(self, conf, executable, requirements):
        if executable == 'same':
            executable = sys.executable

        try:
            executable = os.path.abspath(util.which(executable))

            self._python = util.check_output(
                [executable,
                 '-c',
                 'import sys; '
                 'print(str(sys.version_info[0]) + "." + str(sys.version_info[1]))'
                 ]).strip()
        except (util.ProcessError, OSError, IOError):
            raise EnvironmentUnavailable()

        self._executable = executable
        self._requirements = {}

        super(ExistingEnvironment, self).__init__(conf, executable, requirements)

    @classmethod
    def matches(cls, python):
        if python == 'same':
            python = sys.executable

        try:
            util.which(python)
        except IOError:
            return False
        else:
            return True

    @property
    def name(self):
        return get_env_name(self.tool_name,
                            self._executable.replace(os.path.sep, '_'),
                            {})

    def check_presence(self):
        return True

    def create(self):
        pass

    def _setup(self):
        pass

    def install_project(self, conf, repo, commit_hash=None):
        pass

    def can_install_project(self):
        return False

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return util.check_output([
            self._executable] + args, **kwargs)
