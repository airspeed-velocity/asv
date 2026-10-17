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

from asv.environment import WIN, Environment


def _write_probe(bindir):
    # Windows cannot exec a shebang script (WinError 193), so the probe is a
    # batch file there; util.which finds it through the .bat suffix.
    if WIN:
        exe = bindir / 'asv-pc-probe.bat'
        exe.write_bytes(
            b'@echo off\r\n'
            b'setlocal EnableDelayedExpansion\r\n'
            b'if defined PKG_CONFIG_PATH (\r\n'
            b'  echo(!PKG_CONFIG_PATH!\r\n'
            b') else (\r\n'
            b'  echo UNSET\r\n'
            b')\r\n'
        )
        return
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


def _probe(prefix):
    bindir = prefix / 'bin'
    bindir.mkdir(parents=True, exist_ok=True)
    _write_probe(bindir)
    env = Environment.__new__(Environment)
    env._path = str(prefix)
    env._global_env_vars = {}
    env._install_timeout = 60
    return env


def test_pkg_config_path_prefers_prefix(tmp_path, monkeypatch):
    if WIN:
        first = tmp_path / 'Library' / 'lib' / 'pkgconfig'
        second = tmp_path / 'lib' / 'pkgconfig'
    else:
        first = tmp_path / 'lib' / 'pkgconfig'
        second = tmp_path / 'lib64' / 'pkgconfig'
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / 'python3.pc').write_text('Name: Python\n', encoding='utf-8')
    system = str(tmp_path / 'system' / 'pkgconfig')
    monkeypatch.setenv('PKG_CONFIG_PATH', system)

    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    parts = out.split(os.pathsep)
    assert parts[:2] == [str(first), str(second)]
    assert parts[-1] == system


def test_pkg_config_path_unchanged_without_prefix_files(tmp_path, monkeypatch):
    system = str(tmp_path / 'system' / 'pkgconfig')
    monkeypatch.setenv('PKG_CONFIG_PATH', system)
    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    assert out == system


def test_pkg_config_path_stays_unset_without_prefix_files(tmp_path, monkeypatch):
    monkeypatch.delenv('PKG_CONFIG_PATH', raising=False)
    out = _probe(tmp_path).run_executable('asv-pc-probe', []).strip()
    assert out == 'UNSET'
