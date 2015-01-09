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
import sys

import six

from .console import log
from . import util


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
    # Try the subclasses in reverse order so custom plugins come first
    for cls in list(util.iter_subclasses(Environment))[::-1]:
        if cls.matches(python):
            for env in cls.get_environments(conf, python):
                yield env
            break
    else:
        raise ValueError("No way to create environment for '{0}'".format(python))


class PythonMissingError(BaseException):
    pass


class Environment(object):
    """
    Manage a single environment -- a combination of a particular
    version of Python and a set of dependencies for the benchmarked
    project.

    Environments are created in the
    """
    def __init__(self):
        raise NotImplementedError()

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

    def setup(self):
        """
        Setup the environment on disk.  If it doesn't exist, it is
        created.  Then, all of the requirements are installed into it.
        """
        raise NotImplementedError()

    def install_requirements(self):
        raise NotImplementedError()

    def install(self, package, editable=False):
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

    def install_project(self, conf):
        """
        Install a working copy of the benchmarked project into the
        environment.  Uninstalls any installed copy of the project
        first.
        """
        self.install_requirements()
        self.uninstall(conf.project)
        self.install(os.path.abspath(conf.project))

    def can_install_project(self):
        """
        Return `True` if specific revisions of the benchmarked project
        can be installed into this environment.
        """
        return True

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
    def __init__(self, executable):
        self._executable = executable
        self._python = util.check_output(
            [executable,
             '-c',
             'import sys; '
             'print(str(sys.version_info[0]) + "." + str(sys.version_info[1]))'
         ]).strip()
        self._requirements = {}

    @classmethod
    def get_environments(cls, conf, python):
        if python == 'same':
            python = sys.executable

        yield cls(util.which(python))

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

    def setup(self):
        pass

    def install_requirements(self):
        pass

    def install_project(self, conf):
        pass

    def can_install_project(self):
        return True

    def run(self, args, **kwargs):
        log.debug("Running '{0}' in {1}".format(' '.join(args), self.name))
        return util.check_output([
            self._executable] + args, **kwargs)
