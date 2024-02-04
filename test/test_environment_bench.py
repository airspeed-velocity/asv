import subprocess
import os
import json

import pytest

from . import tools

ENVIRONMENTS = []
if tools.HAS_VIRTUALENV:
    ENVIRONMENTS.append("virtualenv")
if tools.HAS_CONDA:
    ENVIRONMENTS.append("conda")
if tools.HAS_MAMBA:
    ENVIRONMENTS.append("mamba")
if len(ENVIRONMENTS) == 0:
    pytest.skip("No environments can be constructed", allow_module_level=True)

ASV_CONFIG = {
    "version": 1,
    "project": "project",
    "project_url": "http://project-homepage.org/",
    "repo": ".",
    "branches": ["main"],
    "environment_type": "virtualenv",
    "conda_channels": ["conda-forge", "nodefaults"],
    "env_dir": ".asv/env",
    "results_dir": ".asv/results",
    "html_dir": ".asv/html",
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


@pytest.fixture(scope="session", autouse=True)
def setup_asv_project(tmp_path_factory):
    """
    Fixture to set up an ASV project in a temporary directory
    """
    tmp_path = tmp_path_factory.mktemp("asv_project")
    original_dir = os.getcwd()
    os.chdir(tmp_path)

    os.makedirs("benchmarks", exist_ok=True)
    with open("benchmarks/example_bench.py", "w") as f:
        f.write(BENCHMARK_CODE)
    with open("benchmarks/__init__.py", "w") as f:
        f.write("")
    with open("asv.conf.json", "w") as f:
        json.dump(ASV_CONFIG, f, indent=4)
    with open("setup.py", "w") as f:
        f.write(SETUP_CODE)

    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial ASV setup"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_path, check=True)

    yield tmp_path
    os.chdir(original_dir)


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_asv_benchmark(setup_asv_project, env):
    """
    Test running ASV benchmarks in the specified environment.
    """
    project_dir = setup_asv_project
    subprocess.run(["asv", "machine", "--yes"], cwd=project_dir, check=True)
    result = subprocess.run(
        ["asv", "run", "--quick", "--dry-run", "--environment", env],
        cwd=project_dir,
        check=True,
    )

    assert (
        result.returncode == 0
    ), f"ASV benchmark failed in {env} environment: {result.stderr}"
