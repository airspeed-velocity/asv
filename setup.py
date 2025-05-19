#!/usr/bin/env python

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext
from setuptools.errors import CompileError


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
