.. _env-backends:

Optional environment backends
=============================

Core **airspeed velocity** always provides:

- ``virtualenv`` — create isolated envs from interpreters on ``PATH``
- ``existing`` / ``python: "same"`` — run in the current interpreter

Everything else (``conda``, ``rattler``, ``uv``, ``mamba``, ``pixi``, …) is an
**out-of-tree package** discovered at runtime.

Drop-in install
---------------

1. Install ASV (this tree or a release that includes host discovery).
2. Install the backend package into the *same* host environment as ASV.
3. Set ``environment_type`` in ``asv.conf.json``. No ``plugins`` list is
   required when the package registers an entry point.

.. code-block:: sh

   pip install asv
   # one optional backend, e.g. uv (PyPI name when published):
   pip install "asv[uv]"
   # or install the provider package directly:
   # pip install asv_env_uv

.. code-block:: json

   {
     "environment_type": "uv",
     "pythons": ["3.12"]
   }

Discovery
---------

Resolution of ``environment_type`` goes through
:func:`asv.envmgmt.discover.ensure_environment_backend`:

1. Already-registered built-ins (``virtualenv``, ``existing``)
2. Conf ``plugins`` modules (explicit local overrides)
3. Entry points in group ``asv.environment_backends`` (name = type)
4. Optional legacy ``asv_env_<type>`` import only if
   ``ASV_ENV_LEGACY_MODULE_FALLBACK`` is set

Empty ``environment_type`` defaults to ``virtualenv``. Multiple entry
points for the same type fail closed. Missing types raise
:class:`~asv.environment.EnvironmentUnavailable` with a generic install
hint (``pip install "asv[<type>]"`` when that extra exists).

Optional extras
---------------

==============  =================  =====================================
Extra           Package            Notes
==============  =================  =====================================
``asv[conda]``  ``asv_env_conda``  Host ``conda`` CLI
``asv[mamba]``  ``asv_env_mamba``  micromamba/mamba CLI or libmambapy
``asv[rattler]`` ``asv_env_rattler`` maturin wheel over rattler crates
``asv[uv]``     ``asv_env_uv``     maturin wheel over uv-virtualenv crates
``asv[pixi]``   ``asv_env_pixi``   Host ``pixi`` CLI workspace
``asv[envs]``   all of the above   Convenience meta-extra
==============  =================  =====================================

Until a provider is published on the index you use, install it from its
source repository or a built wheel. Maturin packages (``rattler``,
``uv``) need a platform wheel built with ``maturin build --release``.

.. _matrix-layers:

Matrix layers (making ``matrix`` mean something)
------------------------------------------------

Conf ``matrix`` only constrains the environment if later install steps
cannot rewrite those pins. ASV models four layers (bottom → top):

1. **host** — ASV + backend package
2. **matrix** — Python + ``matrix`` requirements / env vars
3. **project** — package under test (``install_command`` / wheel)
4. **runtime** — benchmark execution

Recommended patterns (see also issues `#1542`_, `#1543`_, `#1436`_):

**PyPI-only backends** (``virtualenv``, ``uv``):

- Put dependency pins in ``matrix``.
- Install the project with ``--no-deps`` so the project install does not
  replace matrix pins::

    "install_command": [
      "in-dir={env_dir} python -mpip install --no-deps {wheel_file}"
    ]

**Conda-ecosystem backends** (``conda``, ``mamba``, ``rattler``):

- Prefer pure conda specs in ``matrix``; avoid large ``pip+`` lists when
  possible (conda then pip cannot re-solve together).
- ``pip+`` requirements are always a second mutation.
- Joint conda+PyPI solve is not available in pure rattler yet
  (upstream rattler issue 1044); use ``pixi`` when you need that.

**pixi**:

- Matrix conda deps go into the workspace manifest (one create/solve).
- Matrix ``pip+`` keys are written to ``[pypi-dependencies]`` (simple
  pins) and installed via ``python -m pip`` after ``pixi install`` so
  they are not silently dropped.
- Joint conda+PyPI for the *project wheel* is not automatic yet — still
  prefer ``--no-deps`` for the project layer until a joint install path
  exists.

Helpers live in :mod:`asv.envmgmt.matrix_layers`
(``backend_capabilities``, ``recommend_install_command``,
``matrix_means_something_checklist``).

Writing a backend package
-------------------------

Minimal ``pyproject.toml``::

    [project]
    name = "asv_env_example"
    dependencies = ["asv>=0.6.5"]

    [project.entry-points."asv.environment_backends"]
    example = "asv_env_example:Example"

The class must be a subclass of :class:`asv.environment.Environment`
with ``tool_name = "example"``. Optional capability attributes:

- ``matrix_install_mode``: ``"create"``, ``"post"``, or ``"joint"``
- ``supports_joint_pypi_conda_solve``
- ``supports_joint_pypi_solve``
- ``project_install_prefers_no_deps``
- ``requires_host_tool``

.. _#1542: https://github.com/airspeed-velocity/asv/issues/1542
.. _#1543: https://github.com/airspeed-velocity/asv/issues/1543
.. _#1436: https://github.com/airspeed-velocity/asv/issues/1436
