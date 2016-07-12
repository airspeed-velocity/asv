Installing airspeed velocity
============================

**airspeed velocity** is known to work on Linux, Mac OS-X, and Windows.
It is known to work with Python 2.6, 2.7, 3.2, 3.3, 3.4, and 3.5.
It works also with PyPy.

**airspeed velocity** is a standard Python package, with its
installation based on ``setuptools``, and can be installed using::

    python setup.py install

The requirements should be automatically installed.  If they aren't
installed automatically, for example due to networking restrictions,
the requirements are:

- `six <http://pythonhosted.org/six/>`__, 1.4 or later

One of the following:

- `virtualenv <http://virtualenv.org/>`__, 1.10 or later (this is true
  even with Python 3.3, where virtualenv is included as venv, since
  venv is not compatible with other versions of Python).

  Note that virtualenv 1.11.0 will not work, as it contains a bug in
  setuptools that prevents its installation in a clean virtual
  environment.

- An `anaconda <https://store.continuum.io/cshop/anaconda/>`__ or
  `miniconda <http://conda.pydata.org/miniconda.html>`__
  installation, with the ``conda`` command available on your path.

.. note::

   Anaconda or miniconda is preferred if the dependencies of your
   project involve a lot of compiled C/C++ extensions and are
   available in the ``conda`` repository, since ``conda`` will be able
   to fetch precompiled binaries for these dependencies in many cases.
   Using ``virtualenv``, these dependencies will have to be compiled
   every time the environments are set up.

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

The self tests are based on `py.test <http://pytest.org/>`__.  If you
don't have it installed, and you have a connection to the Internet, it
will be installed automatically.

To run **airspeed velocity**'s self tests::

    python setup.py test

.. todo::
    Checking out from git/tarball/PyPI  etc.
