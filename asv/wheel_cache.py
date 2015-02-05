# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function


import os
import shutil

from . import util


class WheelCache(object):
    def __init__(self, conf, root):
        self._root = root
        self._path = os.path.join(root, 'wheels')
        self._wheel_cache_size = getattr(conf, 'wheel_cache_size', 0)

    def _get_wheel_cache_path(self, commit_hash):
        """
        Get the wheel cache path corresponding to a given commit hash.
        """
        return os.path.join(self._path, commit_hash)

    def _create_wheel_cache_path(self, commit_hash):
        """
        Create the directory for the wheel cache corresponding to the given commit hash.
        """
        path = self._get_wheel_cache_path(commit_hash)
        stamp = os.path.join(path, 'timestamp')
        if not os.path.isdir(path):
            os.makedirs(path)
        with open(stamp, 'wb'):
            pass
        return path

    def _get_wheel(self, commit_hash):
        cache_path = self._get_wheel_cache_path(commit_hash)

        if not os.path.isdir(cache_path):
            return None

        for fn in os.listdir(cache_path):
            if fn.endswith('.whl'):
                return os.path.join(cache_path, fn)
        return None

    def _cleanup_wheel_cache(self):
        if not os.path.isdir(self._path):
            return

        def sort_key(name):
            path = os.path.join(self._path, name, 'timestamp')
            try:
                return os.stat(path).st_mtime
            except OSError:
                return 0

        names = os.listdir(self._path)
        if len(names) < self._wheel_cache_size:
            return

        names.sort(key=sort_key, reverse=True)

        for name in names[self._wheel_cache_size:]:
            path = os.path.join(self._path, name)
            if os.path.isdir(path):
                shutil.rmtree(path)

    def build_project_cached(self, env, package, commit_hash):
        if self._wheel_cache_size == 0:
            return None

        wheel = self._get_wheel(commit_hash)
        if wheel:
            return wheel

        self._cleanup_wheel_cache()

        build_root = env.build_project(commit_hash)
        cache_path = self._create_wheel_cache_path(commit_hash)

        try:
            env._run_executable(
                'pip', ['wheel', '--wheel-dir', cache_path,
                        '--no-deps', '--no-index', build_root])
        except util.ProcessError:
            # failed -- clean up
            shutil.rmtree(cache_path)
            raise

        return self._get_wheel(commit_hash)
