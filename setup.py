#!/usr/bin/env python
import os
import subprocess
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError

from setuptools import setup, Extension
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
    ext_modules = []
    if build_binary:
        ext_modules = ext_modules.append(Extension("asv._rangemedian", ["asv/_rangemedian.cpp"]))

    cmdclass = {'build_ext': optional_build_ext, 'sdist': sdist_checked}

    if BuildDoc is not None:
        cmdclass['build_sphinx'] = BuildDoc

    setup(
        ext_modules=ext_modules,
        cmdclass=cmdclass,
    )


if __name__ == "__main__":
    try:
        run_setup(build_binary=True)
    except BuildFailed:
        print("Compiling asv._rangemedian failed -- continuing without it")
        run_setup(build_binary=False)
