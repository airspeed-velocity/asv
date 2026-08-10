# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Path env handling in asv.benchmark (PYTHONPATH / ASV_PYTHONPATH)."""

import importlib
import sys

import pytest

from asv.benchmark import _apply_path_env


@pytest.fixture
def path_marker(tmp_path, monkeypatch):
    """A unique module importable only via an extra sys.path entry."""
    marker = f"asv1537_marker_{tmp_path.name.replace('-', '_')}"
    root = tmp_path / "pyroot"
    root.mkdir()
    (root / f"{marker}.py").write_text("value = 42\n", encoding="utf-8")
    yield str(root), marker
    sys.modules.pop(marker, None)
    while str(root) in sys.path:
        sys.path.remove(str(root))


def test_pythonpath_kept_when_asv_pythonpath_unset(path_marker, monkeypatch):
    # gh-1537: --python=same + host PYTHONPATH (e.g. scipy build dir)
    root, marker = path_marker
    monkeypatch.setenv("PYTHONPATH", root)
    monkeypatch.delenv("ASV_PYTHONPATH", raising=False)
    # Interpreter startup puts PYTHONPATH on sys.path; simulate that.
    if root not in sys.path:
        sys.path.insert(0, root)

    _apply_path_env()

    mod = importlib.import_module(marker)
    assert mod.value == 42


def test_asv_pythonpath_applied(path_marker, monkeypatch):
    root, marker = path_marker
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.setenv("ASV_PYTHONPATH", root)
    assert root not in sys.path

    _apply_path_env()

    assert root in sys.path
    mod = importlib.import_module(marker)
    assert mod.value == 42


def test_asv_pythonpath_prepended_before_existing(path_marker, monkeypatch, tmp_path):
    root, marker = path_marker
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("ASV_PYTHONPATH", root)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    sys.path.insert(0, str(other))

    _apply_path_env()

    assert sys.path.index(root) < sys.path.index(str(other))
