from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys


# A py.test test command
class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['test']
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name="asv",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'asv = asv.main:main'
        ]
    },

    install_requires=[
        'six>=1.4',
        'virtualenv>=1.10'
    ],

    package_data={
        str('asv'): [
            'www/*.html',
            'www/*.js',
            'www/*.css',
            'www/*.png',
            'www/*.ico',
            'www/jquery/*.js',
            'www/flot/*.js',
            'www/bootstrap/*.js',
            'www/bootstrap/*.css',
            'template/asv.conf.json',
            'template/benchmarks/benchmarks.py'
        ]
    },

    zip_safe=False,

    # py.test testing
    tests_require=['pytest'],
    cmdclass={'test': PyTest},

    author="Michael Droettboom",
    author_email="mdroe@stsci.edu",
    description="Airspeed Velocity: A simple Python history benchmarking tool",
    license="BSD",
    url="http://github.com/spacetelescope/asv"
)
