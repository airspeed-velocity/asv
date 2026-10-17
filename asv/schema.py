from asv import util
import rtoml
import json

from pathlib import Path

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    AnyUrl,
    ConfigDict,
    field_serializer,
)
from typing import Optional, Any, Union
from typing_extensions import Literal


class ASVConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=False)

    @field_serializer("project_url", "repo")
    def serialize_urls(self, _url: Optional[HttpUrl]):
        return str(_url)

    project: str = Field(..., description="The name of the project being benchmarked.")
    project_url: Optional[HttpUrl] = Field(None)
    """
    The URL to the homepage of the project.

    This can point to anywhere, really, as it's only used for the link at the
    top of the benchmark results page back to your project.
    """

    repo: Union[AnyUrl, Path] = Field(...)
    """
    The URL to the repository for the project.

    The value can also be a path, relative to the location of the
    configuration file. For example, if the benchmarks are stored in the
    same repository as the project itself, and the configuration file is
    located at ``benchmarks/asv.conf.json`` inside the repository, you can
    set ``"repo": ".."`` to use the local repository.

    Currently, only ``git`` and ``hg`` repositories are supported, so this must be
    a URL that ``git`` or ``hg`` know how to clone from, for example::

       - git@github.com:airspeed-velocity/asv.git
       - https://github.com/airspeed-velocity/asv.git
       - ssh://hg@bitbucket.org/yt_analysis/yt
       - hg+https://bitbucket.org/yt_analysis/yt

    The repository may be readonly.
    """
    repo_subdir: Optional[str] = Field(None)
    """
    The relative path to your Python project inside the repository.  This is
    where its ``setup.py`` file is located.

    If empty or omitted, the project is assumed to be located at the root of
    the repository.
    """

    build_command: Optional[list[str]] = Field(
        default=[
            "python setup.py build",
            "python -mpip wheel --no-deps --no-index -w {build_cache_dir} {build_dir}",
        ],
        description="Commands to rebuild the project.",
    )
    install_command: Optional[list[str]] = Field(
        default=["in-dir={env_dir} python -mpip install {wheel_file}"],
        description="Command to install the project.",
    )
    uninstall_command: Optional[list[str]] = Field(
        default=["return-code=any python -mpip uninstall -y {project}"],
        description="Command to uninstall the project.",
    )

    branches: Optional[list[str]] = Field(
        None, description="List of branches to benchmark."
    )
    dvcs: Optional[str] = Field(None, description="The DVCS being used (e.g., 'git').")
    environment_type: Optional[str] = Field(
        None, description="The tool to use to create environments (e.g., 'virtualenv')."
    )
    install_timeout: Optional[int] = Field(
        600, description="Timeout in seconds for installing dependencies."
    )
    show_commit_url: Optional[str] = Field(
        None, description="Base URL to show a commit for the project."
    )
    pythons: Optional[list[str]] = Field(
        None, description="List of Python versions to test against."
    )
    conda_channels: Optional[list[str]] = Field(
        None, description="List of conda channels for dependency packages."
    )
    conda_environment_file: Optional[str] = Field(
        None, description="A conda environment file for environment creation."
    )

    matrix: Optional[dict[str, dict[str, Union[list[Optional[str]], None]]]] = Field(
        None,
        description="Matrix of dependencies and environment variables to test.",
    )
    exclude: Optional[list[dict[str, Union[str, dict[str, Optional[str]]]]]] = Field(
        None,
        description="Combinations of libraries/python versions to exclude from testing.",
    )
    include: Optional[list[dict[str, Union[str, dict[str, Optional[str]]]]]] = Field(
        None,
        description="Combinations of libraries/python versions to include for testing.",
    )

    benchmark_dir: Optional[str] = Field(
        None, description="Directory where benchmarks are stored."
    )
    env_dir: Optional[str] = Field(
        None, description="Directory to cache Python environments."
    )
    results_dir: Optional[str] = Field(
        None, description="Directory where raw benchmark results are stored."
    )
    html_dir: Optional[str] = Field(
        None, description="Directory where the HTML tree is written."
    )
    hash_length: Optional[int] = Field(
        8, description="Number of characters to retain in commit hashes."
    )
    build_cache_size: Optional[int] = Field(
        2, description="Number of builds to cache per environment."
    )
    regressions_first_commits: Optional[dict[str, Optional[str]]] = Field(
        None, description="Commits after which regression search starts."
    )
    regressions_thresholds: Optional[dict[str, float]] = Field(
        None,
        description="Thresholds for relative change in results to report regressions.",
    )


# Example usage
config = ASVConfig(
    project="MyProject",
    project_url="https://example.com",
    repo="https://github.com/example/repo",
    matrix={
        "req": {"numpy": ["1.6", "1.7"], "six": ["", None], "pip+emcee": [""]},
        "env": {"ENV_VAR_1": ["val1", "val2"]},
        "env_nobuild": {"ENV_VAR_2": ["val3", None]},
    },
)

# Using model_dump with mode='json' to ensure proper serialization
# print(rtoml.dumps(config.model_dump(mode="toml")))
# print(json.dumps(config.model_dump(mode="toml"), indent=4))
mkconf = ASVConfig.model_validate_json(
    Path("../asv_samples/asv.conf.json").open("rb").read()
)
# exclude_defaults=True to prevents "fat" outputs
print(json.dumps(mkconf.model_dump(mode="toml", exclude_defaults=True), indent=4))
