#!/usr/bin/env python
import os
import subprocess
import ast
from distutils.errors import (DistutilsError, CCompilerError, DistutilsExecError,
                              DistutilsPlatformError)

from setuptools import setup, Extension
from setuptools.command.test import test as TestCommand
from setuptools.command.sdist import sdist
from setuptools.command.build_ext import build_ext


class sdist_checked(sdist):
    """Check git submodules on sdist to prevent incomplete tarballs"""
    def run(self):
        self.__check_submodules()
        sdist.run(self)

    def __check_submodules(self):
        """
        Verify that the submodules are checked out and clean.
        """
        if not os.path.exists('.git'):
            return
        with open('.gitmodules') as f:
            for l in f:
                if 'path' in l:
                    p = l.split('=')[-1].strip()
                    if not os.path.exists(p):
                        raise ValueError('Submodule %s missing' % p)

        proc = subprocess.Popen(['git', 'submodule', 'status'],
                                stdout=subprocess.PIPE)
        status, _ = proc.communicate()
        status = status.decode("ascii", "replace")
        for line in status.splitlines():
            if line.startswith('-') or line.startswith('+'):
                raise ValueError('Submodule not clean: %s' % line)


basedir = os.path.abspath(os.path.dirname(__file__))


def get_version():
    """Parse current version number from __init__.py"""
    # Grab the first assignment to __version__
    version = None
    init_py = os.path.join(os.path.dirname(__file__),
                           'asv', '__init__.py')
    with open(init_py, 'r') as f:
        source = f.read()
    tree = ast.parse(source)
    for statement in tree.body:
        if (isinstance(statement, ast.Assign) and
            len(statement.targets) == 1 and
            statement.targets[0].id == '__version__'):
            version = statement.value.s
            break

    if not version:
        raise RuntimeError("Failed to parse version from {}".format(init_py))

    if 'dev' in version and not version.endswith('.dev'):
        raise RuntimeError("Dev version string in {} doesn't end in .dev".format(
            init_py))

    return version


def get_git_hash():
    """
    Get version from asv/__init__.py and generate asv/_version.py
    """
    # Obtain git revision
    githash = ""
    if os.path.isdir(os.path.join(basedir, '.git')):
        try:
            proc = subprocess.Popen(
                ['git', '-C', basedir, 'rev-parse', 'HEAD'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rev, err = proc.communicate()
            if proc.returncode == 0:
                githash = rev.strip().decode('ascii')
        except OSError:
            pass
    return githash


def get_git_revision():
    """
    Get the number of revisions since the beginning.
    """
    revision = "0"
    if os.path.isdir(os.path.join(basedir, '.git')):
        try:
            proc = subprocess.Popen(
                ['git', '-C', basedir, 'rev-list', '--count', 'HEAD'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rev, err = proc.communicate()
            if proc.returncode == 0:
                revision = rev.strip().decode('ascii')
        except OSError:
            pass
    return revision


def write_version_file(filename, suffix, githash):
    # Write revision file (only if it needs to be changed)
    content = ('__suffix__ = "{0}"\n'
               '__githash__ = "{1}"\n'.format(suffix, githash))

    if not githash.strip():
        # Not in git repository; probably in sdist, so keep old
        # version file
        return

    old_content = None
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            old_content = f.read()

    if content != old_content:
        with open(filename, 'w') as f:
            f.write(content)


class BuildFailed(Exception):
    pass


class optional_build_ext(build_ext):
    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError,
                IOError, ValueError):
            raise BuildFailed()


try:
    # Set default options for setuptools sphinx command;
    # setup(command_options=...) can't specify two builders
    from sphinx.setup_command import BuildDoc as BuildDocSphinx
    class BuildDoc(BuildDocSphinx):
        def initialize_options(self):
            super(BuildDoc, self).initialize_options()
            self.builder = ['html', 'man']
except ImportError:
    BuildDoc = None


def run_setup(build_binary=False):
    version = get_version()
    git_hash = get_git_hash()

    if version.endswith('.dev'):
        suffix = '{0}+{1}'.format(get_git_revision(), git_hash[:8])
        version += suffix
    else:
        suffix = ''

    write_version_file(os.path.join(basedir, 'asv', '_version.py'),
                       suffix, git_hash)

    ext_modules = []
    if build_binary:
        ext_modules = ext_modules.append(Extension("asv._rangemedian", ["asv/_rangemedian.cpp"]))

    cmdclass = {'build_ext': optional_build_ext, 'sdist': sdist_checked}

    if BuildDoc is not None:
        cmdclass['build_sphinx'] = BuildDoc

    setup(
        version=version,
        ext_modules=ext_modules,
        cmdclass=cmdclass,
    )


if __name__ == "__main__":
    try:
        run_setup(build_binary=True)
    except BuildFailed:
        print("Compiling asv._rangemedian failed -- continuing without it")
        run_setup(build_binary=False)
