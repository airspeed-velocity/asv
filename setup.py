#!/usr/bin/env python
import os
import subprocess
from distutils.errors import CompileError

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


class optional_build_ext(build_ext):
    def build_extensions(self):
        try:
            super().build_extensions()
        except CompileError:
            self.extensions = []
            super().build_extensions()


if __name__ == "__main__":
    setup(
        ext_modules=[Extension("asv._rangemedian", ["asv/_rangemedian.cpp"])],
        cmdclass={"build_ext": optional_build_ext, "sdist": sdist_checked},
    )
