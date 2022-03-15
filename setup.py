#!/usr/bin/env python
from distutils.errors import CompileError

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext


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
        cmdclass={"build_ext": optional_build_ext},
    )
