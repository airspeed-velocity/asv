Installing airspeed velocity
============================

**airspeed velocity** is a standard Python package, based on
``setuptools``, and can be installed using::

    python setup.py install

The requirements should be automatically installed.  If they aren't
installed automatically, for example due to networking restrictions,
the requirements are:

    - `six <http://pythonhosted.org/six/>`__

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
