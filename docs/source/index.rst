.. airspeed velocity documentation master file, created by
   sphinx-quickstart on Mon Nov 18 09:12:08 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

airspeed velocity
=================

**airspeed velocity** (``asv``) is a tool for benchmarking Python
packages over their lifetime.  Runtime, memory consumption and even
custom-computed values may be tracked.  The results are displayed in
an interactive web frontend that requires only a basic static
webserver to host.

See an `example airspeed velocity site <http://www.astropy.org/astropy-benchmarks/>`__.

License: `BSD three-clause license
<http://opensource.org/licenses/BSD-3-Clause>`__.

Releases: https://pypi.python.org/pypi/asv

Development: https://github.com/spacetelescope/asv

.. toctree::
   :maxdepth: 1

   installing.rst
   using.rst
   writing_benchmarks.rst
   reference.rst
   dev.rst
   changelog.rst

Credits
-------

Michael Droettboom would like to thank the following contributors to
asv:

.. include:: credits.txt
