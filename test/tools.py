# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

"""
This file contains utilities to generate test repositories.
"""

import datetime
import io
import os
import threading
import time
import six
import tempfile
import sys
from os.path import abspath, join, dirname, relpath, isdir
from contextlib import contextmanager
from distutils.spawn import find_executable
from six.moves import SimpleHTTPServer

import pytest

try:
    import hglib
except ImportError as exc:
    hglib = None

from asv import util
from asv import commands
from asv import config
from asv.commands.preview import create_httpd
from asv.repo import get_repo
from asv.results import Results


try:
    import selenium
    from selenium import webdriver
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException
    HAVE_WEBDRIVER = True
except ImportError:
    HAVE_WEBDRIVER = False

CHROMEDRIVER = [
    'chromedriver',
    '/usr/lib/chromium-browser/chromedriver'   # location on Ubuntu
]

PHANTOMJS = ['phantomjs']

FIREFOX = ['firefox']


def run_asv(*argv):
    parser, subparsers = commands.make_argparser()
    args = parser.parse_args(argv)
    return args.func(args)


def run_asv_with_conf(conf, *argv, **kwargs):
    assert isinstance(conf, config.Config)

    parser, subparsers = commands.make_argparser()
    args = parser.parse_args(argv)

    if sys.version_info[0] >= 3:
        cls = args.func.__self__
    else:
        cls = args.func.im_self

    return cls.run_from_conf_args(conf, args, **kwargs)


# These classes are defined here, rather than using asv/plugins/git.py
# and asv/plugins/mercurial.py since here we need to perform write
# operations to the repository, and the others should be read-only for
# safety.

class Git(object):
    def __init__(self, path):
        self.path = abspath(path)
        self._git = util.which('git')
        self._fake_date = datetime.datetime.now()

    def run_git(self, args, chdir=True, **kwargs):
        if chdir:
            cwd = self.path
        else:
            cwd = None
        kwargs['cwd'] = cwd
        return util.check_output(
            [self._git] + args, **kwargs)

    def init(self):
        self.run_git(['init'])
        self.run_git(['config', 'user.email', 'robot@asv'])
        self.run_git(['config', 'user.name', 'Robotic Swallow'])

    def commit(self, message, date=None):
        if date is None:
            self._fake_date += datetime.timedelta(seconds=1)
            date = self._fake_date

        self.run_git(['commit', '--date', date.isoformat(),
                       '-m', message])

    def tag(self, number):
        self.run_git(['tag', '-a', '-m', 'Tag {0}'.format(number),
                      'tag{0}'.format(number)])

    def add(self, filename):
        self.run_git(['add', relpath(filename, self.path)])

    def checkout(self, branch_name, start_commit=None):
        args = ["checkout"]
        if start_commit is not None:
            args.extend(["-b", branch_name, start_commit])
        else:
            args.append(branch_name)
        self.run_git(args)

    def merge(self, branch_name, commit_message=None):
        self.run_git(["merge", "--no-ff", "--no-commit", "-X", "theirs", branch_name])
        if commit_message is None:
            commit_message = "Merge {0}".format(branch_name)
        self.commit(commit_message)

    def get_hash(self, name):
        return self.run_git(['rev-parse', name]).strip()

    def get_branch_hashes(self, branch=None):
        if branch is None:
            branch = "master"
        return [x.strip() for x in self.run_git(['rev-list', branch]).splitlines()
                if x.strip()]

    def get_commit_message(self, commit_hash):
        return self.run_git(["log", "-n", "1", "--format=%s", commit_hash]).strip()


_hg_config = """
[ui]
username = Robotic Swallow <robot@asv>
"""


class Hg(object):
    def __init__(self, path):
        self._fake_date = datetime.datetime.now()
        self.path = abspath(path)

    def init(self):
        hglib.init(self.path)
        with io.open(join(self.path, '.hg', 'hgrc'), 'w', encoding="utf-8") as fd:
            fd.write(_hg_config)
        self._repo = hglib.open(self.path)

    def commit(self, message, date=None):
        if date is None:
            self._fake_date += datetime.timedelta(seconds=1)
            date = self._fake_date
        date = "{0} 0".format(util.datetime_to_timestamp(date))

        self._repo.commit(message, date=date)

    def tag(self, number):
        self._fake_date += datetime.timedelta(seconds=1)
        date = "{0} 0".format(util.datetime_to_timestamp(self._fake_date))

        self._repo.tag(
            ['tag{0}'.format(number)], message="Tag {0}".format(number),
            date=date)

    def add(self, filename):
        self._repo.add([filename])

    def checkout(self, branch_name, start_commit=None):
        if start_commit is not None:
            self._repo.update(start_commit)
            self._repo.branch(branch_name)
        else:
            self._repo.update(branch_name)

    def merge(self, branch_name, commit_message=None):
        self._repo.merge(branch_name, tool="internal:other")
        if commit_message is None:
            commit_message = "Merge {0}".format(branch_name)
        self.commit(commit_message)

    def get_hash(self, name):
        log = self._repo.log(name, limit=1)
        if log:
            return log[0][1]
        return None

    def get_branch_hashes(self, branch=None):
        if branch is None:
            branch = "default"
        log = self._repo.log('sort(ancestors({0}), -rev)'.format(branch))
        return [entry[1] for entry in log]

    def get_commit_message(self, commit_hash):
        return self._repo.log(commit_hash)[0].desc


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

            try:
                with io.open(src_path, 'r', encoding='utf-8') as fd:
                    content = fd.read()
            except UnicodeDecodeError:
                # File is some sort of binary file...  just copy it
                # directly with no template substitution
                with io.open(src_path, 'rb') as fd:
                    content = fd.read()
                with io.open(dst_path, 'wb') as fd:
                    fd.write(content)
            else:
                content = content.format(**values)
                with io.open(dst_path, 'w', encoding='utf-8') as fd:
                    fd.write(content)

            dvcs.add(dst_path)


def generate_test_repo(tmpdir, values=[0], dvcs_type='git',
                       extra_branches=()):
    """
    Generate a test repository

    Parameters
    ----------
    tmpdir
        Repository directory
    values : list
        List of values to substitute in the template
    dvcs_type : {'git', 'hg'}
        What dvcs to use
    extra_branches : list of (start_commit, branch_name, values)
        Additional branches to generate in the repository.
        For branch start commits, use relative references, e.g.,
        the format 'master~10' or 'default~10' works both for Hg
        and Git.

    Returns
    -------
    dvcs : Git or Hg

    """
    if dvcs_type == 'git':
        dvcs_cls = Git
    elif dvcs_type == 'hg':
        dvcs_cls = Hg
    else:
        raise ValueError("Unknown dvcs type {0}".format(dvcs_type))

    template_path = join(dirname(__file__), 'test_repo_template')

    if not os.path.isdir(tmpdir):
        os.makedirs(tmpdir)
    dvcs_path = tempfile.mkdtemp(prefix='test_repo', dir=tmpdir)
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

    if extra_branches:
        for start_commit, branch_name, values in extra_branches:
            dvcs.checkout(branch_name, start_commit)
            for i, value in enumerate(values):
                mapping = {
                    'version': "{0}".format(i),
                    'dummy_value': value
                }
                copy_template(template_path, dvcs_path, dvcs, mapping)
                dvcs.commit("Revision {0}.{1}".format(branch_name, i))

    return dvcs


def generate_repo_from_ops(tmpdir, dvcs_type, operations):
    if dvcs_type == 'git':
        dvcs_cls = Git
    elif dvcs_type == 'hg':
        dvcs_cls = Hg
    else:
        raise ValueError("Unknown dvcs type {0}".format(dvcs_type))

    template_path = join(dirname(__file__), 'test_repo_template')

    if not os.path.isdir(tmpdir):
        os.makedirs(tmpdir)
    dvcs_path = tempfile.mkdtemp(prefix='test_repo', dir=tmpdir)
    dvcs = dvcs_cls(dvcs_path)
    dvcs.init()

    version = 0
    for op in operations:
        if op[0] == "commit":
            copy_template(template_path, dvcs_path, dvcs, {
                "version": version,
                "dummy_value": op[1],
            })
            version += 1
            dvcs.commit("Revision {0}".format(version), *op[2:])
        elif op[0] == "checkout":
            dvcs.checkout(*op[1:])
        elif op[0] == "merge":
            dvcs.merge(*op[1:])
        else:
            raise ValueError("Unknown dvcs operation {0}".format(op))

    return dvcs


def generate_result_dir(tmpdir, dvcs, values, branches=None):
    result_dir = join(tmpdir, "results")
    os.makedirs(result_dir)
    html_dir = join(tmpdir, "html")
    machine_dir = join(result_dir, "tarzan")
    os.makedirs(machine_dir)

    if branches is None:
        branches = [None]

    conf = config.Config.from_json({
        'results_dir': result_dir,
        'html_dir': html_dir,
        'repo': dvcs.path,
        'project': 'asv',
        'branches': branches or [None],
    })
    repo = get_repo(conf)

    util.write_json(join(machine_dir, "machine.json"), {
        'machine': 'tarzan',
        'version': 1,
    })

    timestamp = datetime.datetime.utcnow()

    params = None
    for commit, value in values.items():
        if isinstance(value, dict):
            params = value["params"]
        result = Results({"machine": "tarzan"}, {}, commit,
                         repo.get_date_from_name(commit), "2.7", None)
        result.add_result("time_func", value, timestamp, timestamp)
        result.save(result_dir)

    util.write_json(join(result_dir, "benchmarks.json"), {
        "time_func": {
            "name": "time_func",
            "params": params or [],
            "param_names": params or [],
        }
    }, api_version=1)
    return conf


@pytest.fixture(scope="session")
def browser(request, pytestconfig):
    """
    Fixture for Selenium WebDriver browser interface
    """
    if not HAVE_WEBDRIVER:
        pytest.skip("Selenium WebDriver Python bindings not found")

    driver_str = pytestconfig.getoption('webdriver')
    driver_options_str = pytestconfig.getoption('webdriver_options')

    # Evaluate the options
    ns = {}
    six.exec_("import selenium.webdriver", ns)
    six.exec_("from selenium.webdriver import *", ns)
    driver_options = eval(driver_options_str, ns)
    driver_cls = getattr(webdriver, driver_str)

    # Find the executable (if applicable)
    paths = []
    if driver_cls is webdriver.Chrome:
        paths += CHROMEDRIVER
        exe_kw = 'executable_path'
    elif driver_cls is webdriver.PhantomJS:
        paths += PHANTOMJS
        exe_kw = 'executable_path'
    elif driver_cls is webdriver.Firefox:
        paths += FIREFOX
        exe_kw = 'firefox_binary'
    else:
        exe_kw = None

    for exe in paths:
        if exe is None:
            continue
        exe = find_executable(exe)
        if exe:
            break
    else:
        exe = None

    if exe is not None and exe_kw is not None and exe_kw not in driver_options:
        driver_options[exe_kw] = exe

    # Create the browser
    browser = driver_cls(**driver_options)

    # Set timeouts
    browser.set_page_load_timeout(10)
    browser.set_script_timeout(10)

    # Clean up on fixture finalization
    def fin():
        browser.quit()
    request.addfinalizer(fin)

    # Set default time to wait for AJAX requests to complete
    browser.implicitly_wait(5)

    return browser


@contextmanager
def preview(base_path):
    """
    Context manager for ASV preview web server. Gives the base URL to use.

    Parameters
    ----------
    base_path : str
        Path to serve files from

    """

    class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            # Don't serve from cwd, but from a different directory
            path = SimpleHTTPServer.SimpleHTTPRequestHandler.translate_path(self, path)
            path = os.path.join(base_path, os.path.relpath(path, os.getcwd()))
            return util.long_path(path)

    httpd, base_url = create_httpd(Handler)

    def run():
        try:
            httpd.serve_forever()
        except:
            import traceback
            traceback.print_exc()
            return

    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    try:
        yield base_url
    finally:
        # Stop must be run in a separate thread, because
        # httpd.shutdown blocks until serve_forever returns.  We don't
        # want to block here --- it appears in some environments
        # problems shutting down the server may arise.
        stopper = threading.Thread(target=httpd.shutdown)
        stopper.daemon = True
        stopper.start()
        stopper.join(5.0)


def get_with_retry(browser, url):
    for j in range(2):
        try:
            return browser.get(url)
        except TimeoutException:
            time.sleep(2)

    return browser.get(url)
