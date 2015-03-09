# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

"""
This file contains utilities to generate test repositories.
"""

import datetime
import io
import os
from os.path import abspath, join, dirname, relpath, isdir

try:
    import hglib
except ImportError as exc:
    hglib = None

from asv import util


# These classes are defined here, rather than using asv/plugins/git.py
# and asv/plugins/mercurial.py since here we need to perform write
# operations to the repository, and the others should be read-only for
# safety.

class Git(object):
    def __init__(self, path):
        self._git = util.which('git')
        self._path = abspath(path)
        self._fake_date = datetime.datetime.now()

    def _run_git(self, args, chdir=True, **kwargs):
        if chdir:
            cwd = self._path
        else:
            cwd = None
        kwargs['cwd'] = cwd
        return util.check_output(
            [self._git] + args, **kwargs)

    def init(self):
        self._run_git(['init'])
        self._run_git(['config', 'user.email', 'robot@asv'])
        self._run_git(['config', 'user.name', 'Robotic Swallow'])

    def commit(self, message):
        # We explicitly override the date here, or the commits
        # will all be in the same second and cause all kinds
        # of problems for asv
        self._fake_date += datetime.timedelta(seconds=1)

        self._run_git(['commit', '--date', self._fake_date.isoformat(),
                       '-m', message])

    def tag(self, number):
        self._run_git(['tag', '-a', '-m', 'Tag {0}'.format(number),
                       'tag{0}'.format(number)])

    def add(self, filename):
        self._run_git(['add', relpath(filename, self._path)])


class Hg(object):
    def __init__(self, path):
        self._fake_date = datetime.datetime.now()
        self._path = abspath(path)

    def init(self):
        hglib.init(self._path)
        self._repo = hglib.open(self._path)

    def commit(self, message):
        # We explicitly override the date here, or the commits
        # will all be in the same second and cause all kinds
        # of problems for asv
        self._fake_date += datetime.timedelta(seconds=1)
        date = "{0} 0".format(util.datetime_to_timestamp(self._fake_date))

        self._repo.commit(message, date=date)

    def tag(self, number):
        self._fake_date += datetime.timedelta(seconds=1)
        date = "{0} 0".format(util.datetime_to_timestamp(self._fake_date))

        self._repo.tag(
            ['tag{0}'.format(number)], message="Tag {0}".format(number),
            date=date)

    def add(self, filename):
        self._repo.add([filename])


def copy_template(src, dst, dvcs, values):
    for root, dirs, files in os.walk(src):
        for dir in dirs:
            src_path = join(root, dir)
            dst_path = join(dst, relpath(src_path, src))
            if not isdir(dst_path):
                os.makedirs(dst_path)

        for file in files:
            src_path = join(root, file)
            dst_path = join(dst, relpath(src_path, src))

            with io.open(src_path, 'r', encoding='utf-8') as fd:
                content = fd.read()
            content = content.format(**values)
            with io.open(dst_path, 'w', encoding='utf-8') as fd:
                fd.write(content)

            dvcs.add(dst_path)


def generate_test_repo(tmpdir, values=[0], dvcs_type='git'):
    if dvcs_type == 'git':
        dvcs_cls = Git
    elif dvcs_type == 'hg':
        dvcs_cls = Hg
    else:
        raise ValueError("Unknown dvcs type {0}".format(dvcs_type))

    template_path = join(dirname(__file__), 'test_repo_template')

    dvcs_path = join(tmpdir, 'test_repo')
    os.makedirs(dvcs_path)
    dvcs = dvcs_cls(dvcs_path)
    dvcs.init()

    for i, value in enumerate(values):
        mapping = {
            'version': i,
            'dummy_value': value
        }

        copy_template(template_path, dvcs_path, dvcs, mapping)

        dvcs.commit("Revision {0}".format(i))
        dvcs.tag(i)

    return dvcs_path
