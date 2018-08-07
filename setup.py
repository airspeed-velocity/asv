#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, Extension, Command
from setuptools.command.test import test as TestCommand

from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError


import os
import shutil
import subprocess
import sys
import ast
try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen


VENDOR_ASSETS = {
    "jquery-1.11.0.min.js": "https://code.jquery.com/jquery-1.11.0.min.js",
    "jquery.flot-0.8.2.min.js": "https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.min.js",
    "jquery.flot-0.8.2.time.min.js": "https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.time.min.js",
    "jquery.flot-0.8.2.selection.min.js": "https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.selection.min.js",
    "jquery.flot-0.8.2.categories.min.js": "https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.categories.min.js",
    "bootstrap-3.1.0.min.js": "https://netdna.bootstrapcdn.com/bootstrap/3.1.0/js/bootstrap.min.js",
    "bootstrap-3.1.0.min.css": "https://netdna.bootstrapcdn.com/bootstrap/3.1.0/css/bootstrap.min.css"
}

VENDOR_DIR = os.path.join(os.path.dirname(__file__), 'asv', 'www', 'vendor')


# A py.test test command
class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test"),
                    ('coverage', 'c', "Generate coverage report")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''
        self.coverage = False

    def finalize_options(self):
        TestCommand.finalize_options(self)

        # The following is required for setuptools<18.4
        try:
            self.test_args = []
        except AttributeError:
            # fails on setuptools>=18.4
            pass
        self.test_suite = 'unused'

    def run_tests(self):
        import pytest
        test_args = ['test']
        if self.pytest_args:
            test_args += self.pytest_args.split()
        if self.coverage:
            test_args += ['--cov', os.path.abspath('asv')]
        errno = pytest.main(test_args)
        sys.exit(errno)


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


def download_assets():
    if not os.path.isdir(VENDOR_DIR):
        os.makedirs(VENDOR_DIR)

    for fn, asset in sorted(VENDOR_ASSETS.items()):
        dst = os.path.join(VENDOR_DIR, fn)

        if os.path.isfile(dst):
            continue

        print("Downloading {0} to asv/www/vendor...".format(asset))

        fsrc = urlopen(asset)
        try:
            with open(dst + ".new", 'wb') as fdst:
                shutil.copyfileobj(fsrc, fdst)
        finally:
            fsrc.close()

        # Usually atomic
        os.rename(dst + ".new", dst)


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

    # Download missing assets
    download_assets()

    # Install entry points for making releases with zest.releaser
    entry_points = {}
    for hook in [('releaser', 'middle'), ('postreleaser', 'before')]:
        hook_ep = 'zest.releaser.' + '.'.join(hook)
        hook_name = 'asv.release.' + '.'.join(hook)
        hook_func = 'asv._release:' + '_'.join(hook)
        entry_points[hook_ep] = ['%s = %s' % (hook_name, hook_func)]

    entry_points['console_scripts'] = ['asv = asv.main:main']

    if build_binary:
        ext_modules = [Extension("asv._rangemedian", ["asv/_rangemedian.cpp"])]
    else:
        ext_modules = []

    with open('README.rst', 'r') as f:
        long_description = f.read()

    setup(
        name="asv",
        version=version,
        packages=['asv',
                  'asv.commands',
                  'asv.plugins',
                  'asv.extern',
                  'asv._release'],
        entry_points=entry_points,
        ext_modules = ext_modules,

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
                'www/flot/*.js',
                'www/vendor/*.css',
                'www/vendor/*.js',
                'template/__init__.py',
                'template/asv.conf.json',
                'template/benchmarks/*.py'
            ]
        },

        python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',

        zip_safe=False,

        # py.test testing
        tests_require=['pytest'],
        cmdclass={'test': PyTest, 'build_ext': optional_build_ext},
        author="Michael Droettboom",
        author_email="mdroe@stsci.edu",
        description="Airspeed Velocity: A simple Python history benchmarking tool",
        license="BSD",
        url="https://github.com/airspeed-velocity/asv",
        long_description=long_description,
        classifiers=[
            'Environment :: Console',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: BSD License',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
            'Topic :: Software Development :: Testing',
        ]
    )


if __name__ == "__main__":
    try:
        run_setup(build_binary=True)
    except BuildFailed:
        print("Compiling asv._rangemedian failed -- continuing without it")
        run_setup(build_binary=False)
