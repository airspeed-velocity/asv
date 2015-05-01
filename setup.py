#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
from setuptools.command.test import test as TestCommand

import os
import subprocess
import sys


# A py.test test command
class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['test']
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


basedir = os.path.abspath(os.path.dirname(__file__))


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
    Get the number of revisions since the last tag.
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


def write_version_file(filename, version, revision):
    # Write revision file (only if it needs to be changed)
    content = '''
__version__ = "{0}"
__githash__ = "{1}"
__release__ = {2}
    '''.format(version, revision, 'dev' in version)

    old_content = None
    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            old_content = f.read()
    if content != old_content:
        with open(filename, 'w') as f:
            f.write(content)


version = '0.1dev'

git_hash = get_git_hash()

# Indicates if this version is a release version
release = 'dev' not in version

if not release:
    version = '{0}{1}+{2}'.format(
        version, get_git_revision(), git_hash[:8])

write_version_file(
    os.path.join(basedir, 'asv', '_version.py'), version, git_hash)


# Install entry points for making releases with zest.releaser
entry_points = {}
for hook in [('releaser', 'middle'), ('postreleaser', 'before'),
             ('postreleaser', 'middle')]:
    hook_ep = 'zest.releaser.' + '.'.join(hook)
    hook_name = 'asv.release.' + '.'.join(hook)
    hook_func = 'asv._release:' + '_'.join(hook)
    entry_points[hook_ep] = ['%s = %s' % (hook_name, hook_func)]

entry_points['console_scripts'] = ['asv = asv.main:main']


setup(
    name="asv",
    version=version,
    packages=['asv',
              'asv.commands',
              'asv.plugins',
              'asv.extern',
              'asv._release'],
    entry_points=entry_points,

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
