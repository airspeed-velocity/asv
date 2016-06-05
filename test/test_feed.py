# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import datetime
import xml.etree.ElementTree as etree
import xml.dom.minidom

import pytest

from asv import feed


try:
    import feedparser
    HAVE_FEEDPARSER = True
except ImportError:
    HAVE_FEEDPARSER = False


try:
    import feedvalidator
    HAVE_FEEDVALIDATOR = True
except ImportError:
    HAVE_FEEDVALIDATOR = False


def prettify_xml(text):
    return xml.dom.minidom.parseString(text).toprettyxml()


def dummy_feed_xml():
    entry_1 = feed.FeedEntry(title='Some title', updated=datetime.datetime.utcnow())
    entry_2 = feed.FeedEntry(title='Another title', updated=datetime.datetime(1990, 1, 1),
                             link='http://foo', content='More text')

    stream = io.BytesIO()
    feed.write_atom(stream, [entry_1, entry_2], author='Me', title='Feed title',
                    address='baz.com')

    return stream.getvalue()


def test_smoketest():
    # Check the result is valid XML and has sensible content
    xml = dummy_feed_xml()
    root = etree.fromstring(xml)
    entries = root.findall('{http://www.w3.org/2005/Atom}entry')
    assert len(entries) == 2


@pytest.mark.skipif(not HAVE_FEEDPARSER, reason="test requires feedparser module")
def test_feedparser():
    # Check the result parses as a feed
    xml = dummy_feed_xml()
    feed = feedparser.parse(xml)

    assert feed['entries'][0]['title'] == 'Some title'
    assert feed['entries'][1]['content'][0]['type'] == 'text/html'
    assert feed['entries'][1]['content'][0]['value'] == 'More text'
    assert feed['entries'][1]['links'] == [{'href': u'http://foo',
                                            'type': u'text/html',
                                            'rel': u'alternate'}]


@pytest.mark.skipif(not HAVE_FEEDVALIDATOR, reason="test requires feedvalidator module")
def test_feedvalidator():
    xml = prettify_xml(dummy_feed_xml())
    result = feedvalidator.validateString(xml)

    ok_messages = (feedvalidator.ValidValue, feedvalidator.MissingSelf)

    assert result['feedType'] == feedvalidator.TYPE_ATOM

    for message in result['loggedEvents']:
        if not isinstance(message, ok_messages):
            print(xml)
            print(message.params)
        assert isinstance(message, ok_messages), message
