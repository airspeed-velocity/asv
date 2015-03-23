#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
from setuptools.command.test import test as TestCommand

import os
import re
import sys
import subprocess


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


def get_version():
    """
    Get version from asv/__init__.py and generate asv/_version.py
    """
    basedir = os.path.abspath(os.path.dirname(__file__))

    # Parse version
    with open(os.path.join(basedir, 'asv', '__init__.py'), 'r') as f:
        for line in f:
            m = re.match('^\\s*__version__\\s*=\\s*["\'](.*)["\']\\s*$', line)
            if m:
                version = m.group(1)
                break

    # Obtain git revision
    revision = ""
    if os.path.isdir(os.path.join(basedir, '.git')):
        try:
            proc = subprocess.Popen(['git', '-C', basedir, 'rev-parse', 'HEAD'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rev, err = proc.communicate()
            if proc.returncode == 0:
                revision = rev.strip()[:8].decode('ascii')
        except OSError:
            pass

    # Write revision file (only if it needs to be changed)
    content = 'revision = "{0}"\n'.format(revision)
    old_content = None
    fn = os.path.join(basedir, 'asv', '_version.py')
    if os.path.isfile(fn):
        with open(fn, 'r') as f:
            old_content = f.read()
    if content != old_content:
        with open(fn, 'w') as f:
            f.write(content)

    # The revision is not added to the version given to setup(), since
    # that disturbs 'setup.py develop'
    return version


setup(
    name="asv",
    version=get_version(),
    packages=['asv',
              'asv.commands',
              'asv.plugins',
              'asv.extern'],
    entry_points={
        'console_scripts': [
            'asv = asv.main:main'
        ]
    },

    install_requires=[
        str('six>=1.4')
    ],

    extras_require={
        str('hg'): ["python-hglib>=1.5"]
    },

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
            'template/__init__.py',
            'template/asv.conf.json',
            'template/benchmarks/*.py'
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
