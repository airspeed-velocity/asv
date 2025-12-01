#!/usr/bin/env python

from setuptools import Extension, setup


if __name__ == "__main__":
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
