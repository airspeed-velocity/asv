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
import shutil
import sys

import six

from .console import log
from .repo import get_repo
from . import util
from . import wheel_cache


def iter_configuration_matrix(matrix):
    """
    Iterate through all combinations of the given configuration
    matrix.
    """
    if len(matrix) == 0:
        yield dict()
        return

    # TODO: Deal with matrix exclusions
    matrix = dict(matrix)
    key = next(six.iterkeys(matrix))
    entry = matrix[key]
    del matrix[key]

    for result in iter_configuration_matrix(matrix):
        if len(entry):
            for value in entry:
                d = dict(result)
                d[key] = value
                yield d
        else:
            d = dict(result)
            d[key] = None
            yield d


def get_env_name(python, requirements):
    """
    Get a name to uniquely identify an environment.
    """
    name = ["py{0}".format(python)]
    reqs = list(six.iteritems(requirements))
    reqs.sort()
    for key, val in reqs:
        if val is not None:
            name.append(''.join([key, val]))
        else:
            name.append(key)
    return '-'.join(name)


def get_environments(conf):
    """
    Iterator returning `Environment` objects for all of the
    permutations of the given versions of Python and a matrix of
    requirements.

    Parameters
    ----------
    conf : dict
        asv configuration object
    """
    for python in conf.pythons:
        for env in get_environments_for_python(conf, python):
            yield env


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
        conf.environment_type = 'existing'

    if conf.environment_type:
        for cls in util.iter_subclasses(Environment):
            if cls.tool_name == conf.environment_type:
                return cls
        raise ValueError(
            "Unknown environment type '{0}'".format(conf.environment_type))
    else:
        log.warn(
            "No `environment_type` specified in asv.conf.json. "
            "This will be required in the future.")
        # Try the subclasses in reverse order so custom plugins come first
        for cls in list(util.iter_subclasses(Environment))[::-1]:
            if cls.matches(python):
                return cls
        raise ValueError(
            "No way to create environment for '{0}'".format(python))


def get_environments_for_python(conf, python):
    """
    Get an iterator of Environment subclasses for the given python
    specifier and all combinations in the configuration matrix.

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
    cls = get_environment_class(conf, python)
    for env in cls.get_environments(conf, python):
        yield env


class PythonMissingError(BaseException):
    pass


class Environment(object):
    """
    Manage a single environment -- a combination of a particular
    version of Python and a set of dependencies for the benchmarked
    project.

    Environments are created in the
    """
    tool_name = None

    def __init__(self, conf):
        self._env_dir = conf.env_dir
        self._path = os.path.abspath(os.path.join(
            self._env_dir, self.hashname))

        self._is_setup = False

        self._repo = get_repo(conf)
        self._cache = wheel_cache.WheelCache(conf, self._path)
        self._build_root = os.path.abspath(os.path.join(self._path, 'project'))

    @classmethod
    def get_environments(cls, conf, python):
        """
        Get all of the environments for the configuration matrix for
        the given Python version specifier.

        Parameters
        ----------
        conf : dict
            asv configuration object

        python : str
            A Python version specifier.  This is the same as passed to
            the `matches` method, and its exact meaning depends on the
            environment.
        """
        raise NotImplementedError()

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
        return get_env_name(self._python, self._requirements)

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

    @property
    def repo(self):
        if not self._is_setup:
            raise ValueError("No repo set up yet")
        return self._repo

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
            'python': self._python,
            'requirements': self._requirements
        }
        if info != expected_info:
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
                shutil.rmtree(self._path)

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
                    shutil.rmtree(self._path)
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

    def checkout_project(self, commit_hash):
        """
        Check out the working tree of the project at given commit hash
        """
        self._repo.checkout(self._build_root, commit_hash)

    def build_project(self, commit_hash):
        self.checkout_project(commit_hash)
        log.info("Building for {0}".format(self.name))
        self.run(['setup.py', 'build'], cwd=self._build_root)
        return self._build_root

    def install_project(self, conf, commit_hash=None):
        """
        Install the benchmarked project into the environment.
        Uninstalls any installed copy of the project first.
        If no specific commit hash is given, one is chosen;
        either a choice that already exist in wheel cache,
        or current master branch in the repository.
        """
        if commit_hash is None:
            commit_hash = self._cache.get_existing_commit_hash()
            if commit_hash is None:
                commit_hash = self.repo.get_hash_from_master()

        self.uninstall(conf.project)

        build_root = self._cache.build_project_cached(
            self, conf, commit_hash)

        if build_root is None:
            build_root = self.build_project(commit_hash)

        self.install(build_root)

    def can_install_project(self):
        """
        Return `True` if specific revisions of the benchmarked project
        can be installed into this environment.
        """
        return True

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
            'python': self._python,
            'requirements': self._requirements
        }
        util.write_json(path, content)


class ExistingEnvironment(Environment):
    tool_name = "existing"

    def __init__(self, conf, executable):
        self._executable = executable
        self._python = util.check_output(
            [executable,
             '-c',
             'import sys; '
             'print(str(sys.version_info[0]) + "." + str(sys.version_info[1]))'
         ]).strip()
        self._requirements = {}

        super(ExistingEnvironment, self).__init__(conf)

    @classmethod
    def get_environments(cls, conf, python):
        if python == 'same':
            python = sys.executable

        yield cls(conf, util.which(python))

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
        return self._executable

    def check_presence(self):
        return True

    def create(self):
        pass

    def _setup(self):
        pass

    def install_project(self, conf, commit_hash=None):
        pass

    def can_install_project(self):
        return False

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return util.check_output([
            self._executable] + args, **kwargs)
