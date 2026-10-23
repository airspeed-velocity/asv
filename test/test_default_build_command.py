# Licensed under a 3-clause BSD style license - see LICENSE.rst

from types import SimpleNamespace

from asv.environment import Environment


def test_default_build_command_runs_only_the_wheel_build(tmp_path):
    calls = []

    class SyntheticRepo:
        @staticmethod
        def get_decorated_hash(commit_hash, length):
            assert commit_hash == "synthetic-commit"
            assert length == 8
            return "synthetic"

    env = SimpleNamespace(
        _build_command=None,
        name="synthetic-env",
        build_env_vars={},
        _interpolate_and_run_commands=lambda commands, **kwargs: calls.append((commands, kwargs)),
    )

    Environment._build_project(env, SyntheticRepo(), "synthetic-commit", str(tmp_path))

    assert calls == [
        (
            ["python -m pip wheel -w {build_cache_dir} {build_dir}"],
            {"default_cwd": str(tmp_path), "extra_env": {}},
        )
    ]
