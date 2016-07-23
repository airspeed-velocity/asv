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
from six.moves.urllib.parse import parse_qs, splitquery, splittag

import pytest
import asv

from asv import config, util

from . import tools
from .tools import browser, get_with_retry


@pytest.fixture(scope="session")
def basic_html(request):
    if hasattr(request.config, 'cache'):
        # Cache the generated html, if py.test is new enough to support it
        cache_dir = request.config.cache.makedir("asv-test_web-basic_html")
        tmpdir = join(six.text_type(cache_dir), 'cached')

        if os.path.isdir(tmpdir):
            # Cached result found
            try:
                if util.load_json(join(tmpdir, 'tag.json')) != [asv.__version__]:
                    raise ValueError()

                html_dir = join(tmpdir, 'html')
                dvcs = tools.Git(join(tmpdir, 'repo'))
                return html_dir, dvcs
            except (IOError, ValueError):
                shutil.rmtree(tmpdir)

        os.makedirs(tmpdir)
    else:
        tmpdir = tempfile.mkdtemp()
        request.addfinalizer(lambda: shutil.rmtree(tmpdir))

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
        first_tested_commit_hash = dvcs.get_hash('master~14')

        repo_path = dvcs.path
        shutil.move(repo_path, join(tmpdir, 'repo'))
        dvcs = tools.Git(join(tmpdir, 'repo'))

        conf = config.Config.from_json({
            'env_dir': join(tmpdir, 'env'),
            'benchmark_dir': join(local, 'benchmark'),
            'results_dir': join(tmpdir, 'results_workflow'),
            'html_dir': join(tmpdir, 'html'),
            'repo': join(tmpdir, 'repo'),
            'dvcs': 'git',
            'project': 'asv',
            'matrix': {},
            'regressions_first_commits': {
                '.*': first_tested_commit_hash
            },
        })

        tools.run_asv_with_conf(conf, 'run', 'ALL',
                                '--show-stderr', '--quick', '--bench=params_examples.*track_.*',
                                _machine_file=machine_file)

        # Swap CPU info and obtain some results
        info = util.load_json(machine_file, api_version=1)
        info['orangutan']['cpu'] = 'Not really fast'
        info['orangutan']['ram'] = 'Not much ram'
        util.write_json(machine_file, info, api_version=1)

        tools.run_asv_with_conf(conf, 'run', 'master~10..', '--steps=3',
                                '--show-stderr', '--quick', '--bench=params_examples.*track_.*',
                                _machine_file=machine_file)

        # Output
        tools.run_asv_with_conf(conf, 'publish')

        shutil.rmtree(join(tmpdir, 'env'))
    finally:
        os.chdir(cwd)

    util.write_json(join(tmpdir, 'tag.json'), [asv.__version__])

    return conf.html_dir, dvcs


def test_web_summarygrid(browser, basic_html):
    html_dir, dvcs = basic_html

    with tools.preview(html_dir) as base_url:
        get_with_retry(browser, base_url)

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


def test_web_regressions(browser, basic_html):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver import ActionChains

    html_dir, dvcs = basic_html

    bad_commit_hash = dvcs.get_hash('master~9')

    browser.set_window_size(1200, 900)

    with tools.preview(html_dir) as base_url:
        get_with_retry(browser, base_url)

        regressions_btn = browser.find_element_by_link_text('Regressions')
        regressions_btn.click()

        # Check that the expected links appear in the table
        regression_1 = browser.find_element_by_link_text('params_examples.track_find_test(1)')
        regression_2 = browser.find_element_by_link_text('params_examples.track_find_test(2)')
        bad_hash_link = browser.find_element_by_link_text(bad_commit_hash[:8])

        href = regression_1.get_attribute('href')
        assert '/#params_examples.track_find_test?' in href
        assert 'commits=' in href

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


def test_web_summarylist(browser, basic_html):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver import ActionChains
    from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

    ignore_exc = (NoSuchElementException, StaleElementReferenceException)

    html_dir, dvcs = basic_html

    last_change_hash = dvcs.get_hash('master~4')

    browser.set_window_size(1200, 900)

    with tools.preview(html_dir) as base_url:
        get_with_retry(browser, base_url)

        summarylist_btn = browser.find_element_by_link_text('Benchmark list')
        summarylist_btn.click()

        # Check text content in the table
        base_link = browser.find_element_by_link_text('params_examples.track_find_test')
        cur_row = base_link.find_element_by_xpath('../..')
        m = re.match('params_examples.track_find_test \\([12]\\) 2.00 \u221233.3% \\(-1.00\\).*'
                         + last_change_hash[:8],
                     cur_row.text)
        assert m, cur_row.text

        # Check link
        base_href, qs = splitquery(base_link.get_attribute('href'))
        base_url, tag = splittag(base_href)
        assert parse_qs(qs) == {'ram': ['128GB'], 'cpu': ['Blazingly fast']}
        assert tag == 'params_examples.track_find_test'

        # Change table sort (sorting is async, so needs waits)
        sort_th = browser.find_element_by_xpath('//th[text()="Recent change"]')
        sort_th.click()
        WebDriverWait(browser, 5).until(
            EC.text_to_be_present_in_element(('xpath', '//tbody/tr[1]'),
                                              'params_examples.track_find_test'))

        # Try to click cpu selector link in the panel
        cpu_select = browser.find_element_by_link_text('Not really fast')
        cpu_select.click()

        # For the other CPU, there is no recent change recorded, only
        # the latest result is available
        def check(*args):
            base_link = browser.find_element_by_link_text('params_examples.track_find_test')
            cur_row = base_link.find_element_by_xpath('../..')
            return cur_row.text in ('params_examples.track_find_test (1) 2.00',
                                    'params_examples.track_find_test (2) 2.00')
        WebDriverWait(browser, 5, ignored_exceptions=ignore_exc).until(check)
