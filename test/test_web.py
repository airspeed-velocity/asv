# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import shutil
import time
import tempfile
from os.path import join, abspath, dirname

import six
import pytest

from asv import config
from asv.commands.run import Run
from asv.commands.publish import Publish

from . import tools
from .tools import browser
from .test_workflow import basic_conf


@pytest.fixture(scope="session")
def basic_html(request):
    tmpdir = tempfile.mkdtemp()
    request.addfinalizer(lambda: shutil.rmtree(tmpdir))

    local = abspath(dirname(__file__))
    cwd = os.getcwd()

    os.chdir(tmpdir)
    try:
        machine_file = join(tmpdir, 'asv-machine.json')

        shutil.copyfile(join(local, 'asv-machine.json'),
                        machine_file)

        dvcs = tools.generate_test_repo(tmpdir, list(range(10)))
        repo_path = dvcs.path

        conf = config.Config.from_json({
            'env_dir': join(tmpdir, 'env'),
            'benchmark_dir': join(local, 'benchmark'),
            'results_dir': join(tmpdir, 'results_workflow'),
            'html_dir': join(tmpdir, 'html'),
            'repo': repo_path,
            'dvcs': 'git',
            'project': 'asv',
            'matrix': {
                "six": [None],
                "psutil": ["1.2", "2.1"]
            }
        })

        Run.run(conf, range_spec="master~5..master", steps=3,
                _machine_file=machine_file, quick=True)
        Publish.run(conf)
    finally:
        os.chdir(cwd)

    return conf, dvcs


def test_web_smoketest(browser, basic_html):
    conf, dvcs = basic_html

    with tools.preview(conf.html_dir) as base_url:
        browser.get(base_url)

        assert browser.title == 'airspeed velocity of an unladen asv'

        # Open a graph display
        browser.find_element_by_link_text('params_examples.track_param').click()

        # Verify there's a plot of some sort
        browser.find_element_by_css_selector('canvas.flot-base')

        # Click a parameterized test button, which should toggle the button
        param_button = browser.find_element_by_link_text('benchmark.params_examples.ClassOne')
        assert 'active' in param_button.get_attribute('class').split()
        param_button.click()
        assert 'active' not in param_button.get_attribute('class').split()

        # Check there's no error popup; needs an explicit wait because
        # there is no event that occurs on successful load that
        # doesn't also occur on a failed load
        time.sleep(1.0)
        error_box = browser.find_element_by_id('error-message')
        assert not error_box.is_displayed()
