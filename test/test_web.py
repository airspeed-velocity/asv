# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import re
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
                "colorama": ["0.3.1", "0.3.3"]
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


def test_web_regressions(browser, tmpdir):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver import ActionChains

    tmpdir = six.text_type(tmpdir)
    local = abspath(dirname(__file__))
    cwd = os.getcwd()

    os.chdir(tmpdir)
    try:
        machine_file = join(tmpdir, 'asv-machine.json')

        shutil.copyfile(join(local, 'asv-machine.json'),
                        machine_file)

        values = [[x]*2 for x in [0, 0, 0, 0, 0,
                                  1, 1, 1, 1, 1,
                                  3, 3, 3, 3, 3,
                                  2, 2, 2, 2, 2]]
        dvcs = tools.generate_test_repo(tmpdir, values)
        repo_path = dvcs.path

        first_tested_commit_hash = dvcs.get_hash('master~14')

        conf = config.Config.from_json({
            'env_dir': join(tmpdir, 'env'),
            'benchmark_dir': join(local, 'benchmark'),
            'results_dir': join(tmpdir, 'results_workflow'),
            'html_dir': join(tmpdir, 'html'),
            'repo': repo_path,
            'dvcs': 'git',
            'project': 'asv',
            'matrix': {},
            'regressions_first_commits': {
                '.*': first_tested_commit_hash
            },
        })

        Run.run(conf, range_spec="ALL", bench='params_examples.track_find_test',
                _machine_file=machine_file, show_stderr=True, quick=True)
        Publish.run(conf)
    finally:
        os.chdir(cwd)

    bad_commit_hash = dvcs.get_hash('master~9')

    with tools.preview(conf.html_dir) as base_url:
        browser.get(base_url)

        regressions_btn = browser.find_element_by_link_text('Show regressions')
        regressions_btn.click()

        # Check that the expected links appear in the table
        regression_1 = browser.find_element_by_link_text('params_examples.track_find_test(1)')
        regression_2 = browser.find_element_by_link_text('params_examples.track_find_test(2)')
        bad_hash_link = browser.find_element_by_link_text(bad_commit_hash[:8])

        href = regression_1.get_attribute('href')
        assert '/#params_examples.track_find_test?' in href
        assert 'time=' in href

        # Sort the tables vs. benchmark name (PhantomJS doesn't allow doing it via actionchains)
        browser.execute_script("$('thead th').eq(0).stupidsort('asc')")
        WebDriverWait(browser, 5).until(EC.text_to_be_present_in_element(
            ('xpath', '//table[1]/tbody/tr[1]/td[1]'), 'params_examples.track_find_test(1)'
            ))

        # Check the contents of the table
        table_rows = browser.find_elements_by_xpath('//table[1]/tbody/tr')
        assert len(table_rows) == 2
        cols1 = [td.text for td in table_rows[0].find_elements_by_xpath('td')]
        cols2 = [td.text for td in table_rows[1].find_elements_by_xpath('td')]

        assert cols1[0] == 'params_examples.track_find_test(1)'
        assert cols2[0] == 'params_examples.track_find_test(2)'

        assert re.match(r'^\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d.\d+Z$', cols1[1])
        assert re.match(r'^\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d.\d+Z$', cols2[1])

        assert cols1[2:] == [bad_commit_hash[:8], '2.00x', '1.00', '2.00', 'Ignore']
        assert cols2[2:] == [bad_commit_hash[:8], '2.00x', '1.00', '2.00', 'Ignore']

        # Check that the ignore buttons work as expected
        buttons = [button for button in browser.find_elements_by_xpath('//button')
                   if button.text == 'Ignore']
        buttons[0].click()

        # The button should disappear, together with the link
        WebDriverWait(browser, 5).until_not(EC.visibility_of(buttons[0]))
        WebDriverWait(browser, 5).until_not(EC.visibility_of(regression_1))

        table_rows = browser.find_elements_by_xpath('//table[1]/tbody/tr')
        assert len(table_rows) == 1

        # There's a second button for showing the links, clicking
        # which makes the elements reappear
        show_button = [button for button in browser.find_elements_by_xpath('//button')
                       if button.text == 'Show ignored regressions...'][0]
        show_button.click()

        regression_1 = browser.find_element_by_link_text('params_examples.track_find_test(1)')
        WebDriverWait(browser, 5).until(EC.visibility_of(regression_1))

        table_rows = browser.find_elements_by_xpath('//table[2]/tbody/tr')
        assert len(table_rows) == 1

        # There's a config sample element
        pre_div = browser.find_element_by_xpath('//pre')
        assert "params_examples\\\\.track_find_test\\\\(1\\\\)" in pre_div.text

        # There's an unignore button that moves the element back to the main table
        unignore_button = [button for button in browser.find_elements_by_xpath('//button')
                           if button.text == 'Unignore'][0]
        unignore_button.click()

        browser.find_elements_by_xpath('//table[1]/tbody/tr[2]') # wait until the table has two rows

        table_rows = browser.find_elements_by_xpath('//table[1]/tbody/tr')
        assert len(table_rows) == 2

        # Check that a plot of some sort appears on mouseover.  The
        # page needs to be scrolled first so that the mouseover popup
        # has enough space to appear.
        regression_1 = browser.find_element_by_link_text('params_examples.track_find_test(1)')

        y = regression_1.location['y']
        browser.execute_script('window.scrollTo(0, {0})'.format(y - 200))

        chain = ActionChains(browser)
        chain.move_to_element(regression_1)
        chain.perform()

        popover = browser.find_element_by_css_selector('div.popover-content')
        flotplot = browser.find_element_by_css_selector('canvas.flot-base')
