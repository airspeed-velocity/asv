# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Matrix layer model and backend capability flags."""

from asv import environment as envmod
from asv.envmgmt import matrix_layers as ml
from asv.plugins.virtualenv import Virtualenv


def test_layers_order():
    assert ml.LAYERS == (
        ml.LAYER_HOST,
        ml.LAYER_MATRIX,
        ml.LAYER_PROJECT,
        ml.LAYER_RUNTIME,
    )


def test_virtualenv_capabilities_match_class():
    caps = ml.backend_capabilities("virtualenv", Virtualenv)
    assert caps["matrix_install_mode"] == ml.MATRIX_INSTALL_CREATE
    assert caps["supports_joint_pypi_solve"] is True
    assert caps["project_install_prefers_no_deps"] is True
    assert Virtualenv.project_install_prefers_no_deps is True


def test_existing_capabilities():
    caps = ml.backend_capabilities("existing", envmod.ExistingEnvironment)
    assert caps["supports_joint_pypi_solve"] is False


def test_known_optional_backends_documented():
    for tool in ("conda", "mamba", "rattler", "uv", "pixi"):
        assert tool in ml.KNOWN_BACKEND_CAPABILITIES
        caps = ml.backend_capabilities(tool)
        assert caps["matrix_install_mode"] in ml.MATRIX_INSTALL_MODES


def test_recommend_install_command_no_deps():
    cmd = ml.recommend_install_command("uv")
    assert cmd is not None
    assert any("--no-deps" in c for c in cmd)


def test_recommend_install_command_conda_none():
    # conda default table: project_install_prefers_no_deps False
    assert ml.recommend_install_command("conda") is None


def test_checklist_mentions_joint_and_project():
    notes = ml.matrix_means_something_checklist("rattler")
    assert "matrix_layer" in notes
    assert "joint_conda_pypi" in notes
    assert "project_layer" in notes
    assert "1044" in notes["joint_conda_pypi"] or "joint" in notes["joint_conda_pypi"].lower()


def test_checklist_flags_install_without_no_deps():
    class Conf:
        install_command = ["in-dir={env_dir} python -mpip install {wheel_file}"]

    notes = ml.matrix_means_something_checklist("virtualenv", Conf())
    assert "install_command" in notes
    assert "--no-deps" in notes["install_command"] or "overwrite" in notes["install_command"]
