Installing airspeed velocity
============================

**airspeed velocity** is known to work on Linux, Mac OS-X, and Windows.
It is known to work with Python 3.7 and higher.
It works also with PyPy.

**airspeed velocity** is a standard Python package, and the latest
released version may be `installed in the standard
way from PyPI <https://packaging.python.org/tutorials/installing-packages/>`__::

    pip install asv

The development version can be installed by cloning the source
repository and running ``pip install .`` inside it, or by ``pip
install git+https://github.com/airspeed-velocity/asv``.

The requirements should be automatically installed.  If they aren't
installed automatically, for example due to networking restrictions,
the ``python`` requirements are as noted in the ``pyproject.toml``.

Environment backends
--------------------

ASV creates isolated environments to build and run benchmarks.  At least
one backend must be usable on your machine; which ones you need depends
on ``environment_type`` in :doc:`asv.conf.json` (see :ref:`environments`).

Shipped with ASV (under ``asv.plugins``):

- **virtualenv** — requires the `virtualenv
  <https://virtualenv.pypa.io/>`__ package (declared as a dependency of
  ASV).  Interpreters listed in ``pythons`` must already exist on
  ``PATH`` (for example ``python3.12``); ASV does not download Python
  versions for you.

- **conda** — requires a `Miniconda <https://docs.conda.io/en/latest/miniconda.html>`__,
  `Miniforge <https://conda-forge.org/download/>`__, or similar install
  with the ``conda`` command on ``PATH``.  Optional related settings:
  ``conda_channels``, ``conda_environment_file``.

- **mamba** — uses **libmambapy** (the libmamba Python API), not only the
  ``mamba`` CLI.  Typical install is from conda-forge together with a
  working conda-compatible stack (``conda`` / ``conda-build`` as required
  by your platform).  See the `libmambapy documentation
  <https://mamba.readthedocs.io/en/latest/python_api.html>`__.

Additional backends can be provided by third-party modules listed in the
``plugins`` configuration key (see :ref:`conf-plugins`).

.. note::

   For non-Python (native) dependencies, **conda** or **mamba** are often
   preferable because binaries can be installed from channels such as
   conda-forge.  With **virtualenv**, packages without wheels must be
   compiled when environments are created, which is slower.

Optional optimization
---------------------

If your project being benchmarked contains C, C++, Objective-C or
Cython, consider installing ``ccache``.  `ccache
<https://ccache.samba.org/>`__ is a compiler cache that speeds up
compilation time when the same objects are repeatedly compiled.  In
**airspeed velocity**, the project being benchmarked is recompiled at
many different points in its history, often with only minor changes to
the source code, so ``ccache`` can help speed up the total benchmarking
time considerably.

Running the self-tests
----------------------


The self tests are based on `pytest <https://docs.pytest.org/>`__.  If you
don't have it installed, and you have a connection to the Internet, it
will be installed automatically.

To run **airspeed velocity**'s self tests::

    pytest
