# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""PKG_CONFIG_PATH isolation in Environment.run_executable.

A conda/rattler prefix can place a sysrooted compiler on PATH while
pkg-config still resolves python3 to the system .pc file. Meson's
Cython sanity check then compiles against distro headers the conda
compiler cannot see. virtualenv and uv use the same run_executable
path and must keep a prefix with no pkgconfig directory unchanged.
"""

import os
import stat

from asv.environment import Environment


def _probe(prefix):
    bindir = prefix / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / 'asv-pc-probe'
    exe.write_text(
        '#!/bin/sh\n'
        'if [ -z "${PKG_CONFIG_PATH+x}" ]; then\n'
        '  printf "UNSET\\n"\n'
        'else\n'
        '  printf "%s\\n" "$PKG_CONFIG_PATH"\n'
        'fi\n',
        encoding='utf-8',
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    env = Environment.__new__(Environment)
    env._path = str(prefix)
    env._global_env_vars = {}
    env._install_timeout = 60
    return env


def test_pkg_config_path_prefers_prefix(tmp_path, monkeypatch):
    pc = tmp_path / 'lib' / 'pkgconfig'
    pc.mkdir(parents=True)
    lib64 = tmp_path / 'lib64' / 'pkgconfig'
    lib64.mkdir(parents=True)
    (pc / 'python3.pc').write_text('Name: Python\n', encoding='utf-8')
    monkeypatch.setenv('PKG_CONFIG_PATH', '/usr/lib/pkgconfig')

    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    parts = out.split(os.pathsep)
    assert parts[:2] == [str(pc), str(lib64)]
    assert parts[-1] == '/usr/lib/pkgconfig'


def test_pkg_config_path_unchanged_without_prefix_files(tmp_path, monkeypatch):
    monkeypatch.setenv('PKG_CONFIG_PATH', '/usr/lib/x86_64-linux-gnu/pkgconfig')
    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    assert out == '/usr/lib/x86_64-linux-gnu/pkgconfig'


def test_pkg_config_path_stays_unset_without_prefix_files(tmp_path, monkeypatch):
    monkeypatch.delenv('PKG_CONFIG_PATH', raising=False)
    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    assert out == 'UNSET'
