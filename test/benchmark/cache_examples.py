# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os
import time


class ClassLevelSetup:
    def setup_cache(self):
        return [0] * 500

    def track_example(self, big_list):
        return len(big_list)

    def track_example2(self, big_list):
        return len(big_list)


def setup_cache():
    with open("data.txt", "wb") as fd:
        fd.write(b"42\n")
    return {'foo': 42, 'bar': 12}


def track_cache_foo(d):
    assert os.path.isfile("data.txt")
    with open("data.txt", "rb") as fd:
        assert fd.read().strip() == b'42'
    return d['foo']


def track_cache_bar(d):
    return d['bar']


def my_setup_cache():
    return {'foo': 0, 'bar': 1}


def track_my_cache_foo(d):
    assert not os.path.isfile("data.txt")
    return d['foo']
track_my_cache_foo.setup_cache = my_setup_cache


class ClassLevelSetupFail:
    def setup_cache(self):
        raise RuntimeError()

    def track_fail(self):
        return -1


class ClassLevelCacheTimeout:
    def setup_cache(self):
        time.sleep(2.0)

    setup_cache.timeout = 0.1

    def track_fail(self):
        return 0


class ClassLevelCacheTimeoutSuccess:
    timeout = 2.0

    def setup_cache(self):
        time.sleep(2.0)

    setup_cache.timeout = 5.0

    def track_success(self):
        return 0

