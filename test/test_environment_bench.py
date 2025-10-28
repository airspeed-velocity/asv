import json
import os
import subprocess

import pytest

from asv import util

from . import tools

ENVIRONMENTS = []
if tools.HAS_VIRTUALENV:
    ENVIRONMENTS.append("virtualenv")
if tools.HAS_CONDA:
    ENVIRONMENTS.append("conda")
if tools.HAS_RATTLER:
    ENVIRONMENTS.append("rattler")
if tools.HAS_UV:
    ENVIRONMENTS.append("uv")
if len(ENVIRONMENTS) == 0:
    pytest.skip("No environments can be constructed", allow_module_level=True)

ASV_CONFIG = {
    "version": 1,
    "project": "project",
    "project_url": "https://project-homepage.org/",
    "repo": ".",
    "branches": ["main"],
    "environment_type": "virtualenv",
    "conda_channels": ["conda-forge", "nodefaults"],
    "env_dir": ".asv/env",
    "results_dir": ".asv/results",
    "html_dir": ".asv/html",
    "matrix": {
        "asv_runner": [],  # On conda-forge, not defaults
    },
}

BENCHMARK_CODE = """
class ExampleBench:
    def setup(self):
        self.data = list(range(100))

    def time_sum(self):
        return sum(self.data)

    def time_max(self):
        return max(self.data)
"""

SETUP_CODE = """
from setuptools import setup, find_packages

setup(
    name="myproject",
    version="0.1.0",
    packages=find_packages(),
)
"""

CONDARC_CONTENT = """
channels:
  - conda-forge
  - nodefaults
channel_priority: disabled
auto_activate_base: false
"""

ALT_CONDARC_CONTENT = """
channels:
  - https://repo.prefix.dev/bioconda
"""


@pytest.fixture(scope="session")
def asv_project_factory(tmp_path_factory):
    """
    Factory to set up an ASV project with customizable configurations.
    """

    def _create_asv_project(custom_config=None, create_condarc=False, alt_condarc=False):
        tmp_path = tmp_path_factory.mktemp("asv_project")
        original_dir = os.getcwd()
        os.chdir(tmp_path)

        os.makedirs("benchmarks", exist_ok=True)
        benchmark_file = tmp_path / "benchmarks" / "example_bench.py"
        benchmark_file.write_text(BENCHMARK_CODE)
        (tmp_path / "benchmarks" / "__init__.py").write_text("")

        config = ASV_CONFIG.copy()
        if custom_config:
            config.update(custom_config)
        (tmp_path / "asv.conf.json").write_text(json.dumps(config, indent=4))
        (tmp_path / "setup.py").write_text(SETUP_CODE)

        if create_condarc:
            content = ALT_CONDARC_CONTENT if alt_condarc else CONDARC_CONTENT
            (tmp_path / ".condarc").write_text(content)

        subprocess.run(["git", "init"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial ASV setup"], cwd=tmp_path, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, check=True)

        os.chdir(original_dir)
        return tmp_path

    return _create_asv_project


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_asv_benchmark(asv_project_factory, env):
    """
    Test running ASV benchmarks in the specified environment.
    """
    if util.ON_PYPY and env in ["rattler"]:
        pytest.skip("py-rattler only works for CPython")
    project_dir = asv_project_factory(custom_config={})
    subprocess.run(["asv", "machine", "--yes"], cwd=project_dir, check=True)
    result = subprocess.run(
        ["asv", "run", "--quick", "--dry-run", "--environment", env],
        cwd=project_dir,
        check=True,
    )

    assert result.returncode == 0, f"ASV benchmark failed in {env} environment: {result.stderr}"


@pytest.mark.parametrize(
    ("environment", "config_modifier", "expected_success", "expected_error"),
    [
        pytest.param(
            env,
            {"conda_channels": ["conda-forge", "nodefaults"]},
            True,
            None,
            id=f"with_conda_forge_{env}",
            marks=[
                pytest.mark.skipif(
                    env == "rattler" and not tools.HAS_RATTLER, reason="needs rattler"
                ),
            ],
        )
        for env in ["rattler"]
    ]
)
def test_asv_rattler(
    environment, asv_project_factory, config_modifier, expected_success, expected_error
):
    """
    Test running ASV benchmarks with various configurations,
    checking for specific errors when failures are expected.
    """
    if util.ON_PYPY:
        pytest.skip("py-rattler only works for CPython")
    project_dir = asv_project_factory(custom_config=config_modifier)
    try:
        subprocess.run(
            ["asv", "run", "--quick", "--dry-run", "--environment", environment],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if not expected_success:
            pytest.fail("Expected failure, but succeeded")
    except subprocess.CalledProcessError as exc:
        if expected_success:
            pytest.fail(f"ASV benchmark unexpectedly failed: {exc.stderr}")
        elif expected_error and all(err not in exc.stderr for err in expected_error):
            pytest.fail(f"Expected error '{expected_error}' not found in stderr: {exc.stderr}")


pytest.mark.skipif(not tools.HAS_RATTLER)
def test_condarc_channel_rattler(asv_project_factory):
    os.environ["ASV_USE_CONDARC"] = "1"
    os.environ["CONDARC"] = ".condarc"
    project_dir = asv_project_factory(custom_config={"conda_channels": ["conda-forge"], "matrix": {"snakemake-minimal": [], "python": ["3.12"]}}, create_condarc=True, alt_condarc=True)
    # snakemake-minimal ensures we pick up bioconda from .condarc
    subprocess.run(
        ["asv", "run", "--quick", "--dry-run", "--environment", "rattler"],
        cwd=project_dir,
        check=True,
        capture_output=True,
        text=True,
    )
