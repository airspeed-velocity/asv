#!/usr/bin/env python

from setuptools import Extension, setup
import sysconfig


if __name__ == "__main__":
    if sysconfig.get_config_var("Py_GIL_DISABLED") == 1:
        # Cannot build a limited API extension module for free-threaded builds
        setup(
            ext_modules=[
                Extension(
                    "asv._rangemedian",
                    sources=["asv/_rangemedian.cpp"],
                )
            ],
        )
    else:
        setup(
            ext_modules=[
                Extension(
                    "asv._rangemedian",
                    sources=["asv/_rangemedian.cpp"],
                    define_macros=[("Py_LIMITED_API", "0x03060000")],
                    py_limited_api=True,
                )
            ],
            options={"bdist_wheel": {"py_limited_api": "cp36"}},
        )
    else:
