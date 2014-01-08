Installing airspeed velocity
============================

**airspeed velocity** is known to work on Linux and Mac OS-X.  It's
highly unlikely that it works on Microsoft Windows.  It is known to
work with Python 2.6, 2.7, 3.2 and 3.3.

**airspeed velocity** is a standard Python package, with its
installation based on ``setuptools``, and can be installed using::

    python setup.py install

The requirements should be automatically installed.  If they aren't
installed automatically, for example due to networking restrictions,
the requirements are:

    - `six <http://pythonhosted.org/six/>`__, 1.4 or later

    - `virtualenv <http://virtualenv.org/>`__, 1.10 or later (this is
      true even with Python 3.3, where virtualenv is included as venv,
      since venv is not compatible with other versions of Python).

Optional dependencies, required only to determine machine information:

    - `psutil <https://code.google.com/p/psutil/>`__

    - `numpy <http://www.numpy.org/>`__

Running the self-tests
----------------------

The self tests are based on `py.test <http://pytest.org/>`__.  If you
don't have it installed, and you have a connection to the Internet, it
will be installed automatically.

To run **airspeed velocity**'s self tests::

    python setup.py test

.. todo::
    Checking out from git/tarball/PyPI  etc.
