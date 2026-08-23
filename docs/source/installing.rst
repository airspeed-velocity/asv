Installing airspeed velocity
============================

**airspeed velocity** is known to work on Linux, MacOS, and Windows, for Python
3.9 and higher. PyPy 3.10 is also supported.

**airspeed velocity** is a standard Python package, and the latest released
version may be `installed from PyPI
<https://packaging.python.org/tutorials/installing-packages/>`__:

.. code-block:: sh

    pip install asv

The development version can be installed from GitHub:

.. code-block:: sh

   git clone git@github.com:airspeed-velocity/asv
   cd asv
   pip install .
   # Or in one shot
   pip install git+https://github.com/airspeed-velocity/asv

The basic requirements should be automatically installed.  If they aren't
installed automatically, for example due to networking restrictions, the
``python`` requirements are as noted in the ``pyproject.toml``.

Environment backends
--------------------

**Built-in** (always available with ``pip install asv``):

- `virtualenv <https://virtualenv.pypa.io/>`__ — default when
  ``environment_type`` is empty. Uses interpreters already on ``PATH``.

**Optional** backends are separate packages. Install the matching extra
(or the package itself) into the *host* environment that runs ``asv``::

    pip install "asv[uv]"       # or asv[conda], asv[rattler], asv[mamba], asv[pixi]
    # then set "environment_type": "uv" in asv.conf.json

See :ref:`env-backends` for discovery rules, matrix layers, and how to
author a backend package.

.. note::

   Prefer a solver-backed backend (``rattler``, ``pixi``, or ``uv``) when
   non-trivial dependency matrices matter. Classic ``conda`` remains
   useful for environment.yml workflows but applies pip after conda
   without a joint solve. Plain ``virtualenv`` is enough for pure-Python
   projects with interpreters already installed.

Optional optimizations
----------------------

If your project being benchmarked contains C, C++, Objective-C or Cython,
consider installing ``ccache``.  `ccache <https://ccache.samba.org/>`__ is a
compiler cache that speeds up compilation time when the same objects are
repeatedly compiled.

In **airspeed velocity**, the project being benchmarked is recompiled at many
different points in its history, often with only minor changes to the source
code, so ``ccache`` can help speed up the total benchmarking time considerably.

Running the self-tests
----------------------

The testsuite is based on `pytest <https://docs.pytest.org/>`__.

To run **airspeed velocity**'s testsuite::

    pytest
