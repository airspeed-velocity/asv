# Licensed under a 3-clause BSD style license - see LICENSE.rst

from io import StringIO
from pathlib import Path

from asv import util
from asv.commands.quickstart import Quickstart, _merge_gitignore

from . import tools


def test_quickstart(tmpdir, monkeypatch):
    dest = Path(tmpdir, "separate")
    dest.mkdir()

    tools.run_asv("quickstart", "--no-top-level", "--dest", str(dest))

    asv_conf_path = dest / "asv.conf.json"
    assert asv_conf_path.exists()
    benchmark_path = dest / "benchmarks" / "benchmarks.py"
    assert benchmark_path.exists()

    conf = util.load_json(str(asv_conf_path), js_comments=True)
    assert "env_dir" not in conf
    assert "html_dir" not in conf
    assert "results_dir" not in conf

    dest = Path(tmpdir, "same")
    dest.mkdir()

    monkeypatch.setattr("sys.stdin", StringIO("1"))
    tools.run_asv("quickstart", "--dest", str(dest))

    asv_conf_path = dest / "asv.conf.json"
    assert asv_conf_path.exists()
    benchmark_path = dest / "benchmarks" / "benchmarks.py"
    assert benchmark_path.exists()

    conf = util.load_json(str(asv_conf_path), js_comments=True)
    assert conf["env_dir"] != "env"
    assert conf["html_dir"] != "html"
    assert conf["results_dir"] != "results"


def test_quickstart_with_existing_gitignore(tmpdir):
    """Upstream #1582: existing .gitignore must not block suite creation."""
    dest = Path(tmpdir, "preexisting_gitignore")
    dest.mkdir()
    gitignore = dest / ".gitignore"
    gitignore.write_text("# project local\n*.local\n", encoding="utf-8")

    rc = Quickstart.run(dest=str(dest), top_level=True)
    assert rc is None or rc == 0

    assert (dest / "asv.conf.json").is_file()
    assert (dest / "benchmarks" / "benchmarks.py").is_file()
    text = gitignore.read_text(encoding="utf-8")
    assert "*.local" in text
    # Template ignores bytecode; ensure merge brought ASV patterns in.
    assert "__pycache__/" in text or "*.py[cod]" in text

    conf = util.load_json(str(dest / "asv.conf.json"), js_comments=True)
    assert conf.get("repo") == "."


def test_quickstart_still_fails_on_real_conflict(tmpdir):
    dest = Path(tmpdir, "conflict")
    dest.mkdir()
    (dest / "asv.conf.json").write_text("{}\n", encoding="utf-8")

    rc = Quickstart.run(dest=str(dest), top_level=False)
    assert rc == 1
    # Must not overwrite user conf with template copy when conflict detected first.
    assert (dest / "asv.conf.json").read_text(encoding="utf-8") == "{}\n"


def test_merge_gitignore_appends_missing_only(tmp_path):
    template = tmp_path / "template.gitignore"
    template.write_text("a\nb\nc\n", encoding="utf-8")
    dest = tmp_path / "dest.gitignore"
    dest.write_text("b\n", encoding="utf-8")

    assert _merge_gitignore(str(template), str(dest)) is True
    body = dest.read_text(encoding="utf-8")
    assert body.count("\nb\n") + (1 if body.startswith("b\n") else 0) >= 1
    assert "a" in body.splitlines()
    assert "c" in body.splitlines()
    # Second merge is a no-op for already-present lines.
    assert _merge_gitignore(str(template), str(dest)) is False
