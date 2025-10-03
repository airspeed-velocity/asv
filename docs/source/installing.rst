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

For managing the environments, one of the following packages is required:

- `py-rattler <https://conda.github.io/rattler/py-rattler/>`__, which is used
  for the new ``rattler`` backend.

- `virtualenv <https://virtualenv.pypa.io/>`__, which is required since
  venv is not compatible with other versions of Python.

- An `anaconda <https://www.anaconda.com/download>`__ or
  `miniconda <https://www.anaconda.com/docs/getting-started/miniconda/>`__
  installation, with the ``conda`` command available on your path.

.. note::

   ``rattler`` is the fastest for situations where non-pythonic
   dependencies are required. Anaconda or miniconda is slower but
   still preferred if the project involves a lot of compiled C/C++
   extensions and are available in the ``conda`` repository, since
   ``conda`` will be able to fetch precompiled binaries for these
   dependencies in many cases. Using ``virtualenv``, dependencies
   without precompiled wheels usually have to be compiled every
   time the environments are set up.

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
