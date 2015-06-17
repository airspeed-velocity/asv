# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function


class ClassLevelSetup:
    def setup_cache(self):
        return [0] * 500

    def teardown_cache(self):
        pass

    def track_example(self, big_list):
        return len(big_list)

    def track_example2(self, big_list):
        return len(big_list)


def setup_cache():
    return {'foo': 42, 'bar': 12}


def track_cache_foo(d):
    return d['foo']


def track_cache_bar(d):
    return d['bar']


def my_setup_cache():
    return {'foo': 0, 'bar': 1}


def track_my_cache_foo(d):
    return d['foo']
track_my_cache_foo.setup_cache = my_setup_cache
