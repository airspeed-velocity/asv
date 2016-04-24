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

    def _get_cache_contents(self):
        """
        Return list of commit hash directories in the cache (containing
        wheels or not), sorted by decreasing timestamp
        """
        if not os.path.isdir(self._path):
            return []

        def sort_key(name):
            path = os.path.join(self._path, name, 'timestamp')
            try:
                return os.stat(path).st_mtime
            except OSError:
                return 0

        names = os.listdir(self._path)
        names.sort(key=sort_key, reverse=True)
        return names

    def _cleanup_wheel_cache(self):
        names = self._get_cache_contents()
        for name in names[self._wheel_cache_size:]:
            path = os.path.join(self._path, name)
            if os.path.isdir(path):
                util.long_path_rmtree(path)

    def build_project_cached(self, env, package, repo, commit_hash):
        if self._wheel_cache_size == 0:
            return None

        wheel = self._get_wheel(commit_hash)
        if wheel:
            return wheel

        self._cleanup_wheel_cache()

        build_root = env.build_project(repo, commit_hash)
        cache_path = self._create_wheel_cache_path(commit_hash)

        try:
            env.run_executable(
                'pip', ['wheel', '--wheel-dir', cache_path,
                        '--no-deps', '--no-index', build_root])
        except util.ProcessError:
            # failed -- clean up
            util.long_path_rmtree(cache_path)
            raise

        return self._get_wheel(commit_hash)

    def get_existing_commit_hash(self):
        """
        Return a commit hash for which a wheel already exists,
        or None if none is found.
        """
        names = self._get_cache_contents()

        for commit_hash in names[:self._wheel_cache_size]:
            names = os.listdir(os.path.join(self._path, commit_hash))
            if any(name.endswith('.whl') for name in names):
                return commit_hash

        return None
