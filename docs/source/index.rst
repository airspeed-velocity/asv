.. airspeed velocity documentation master file, created by
   sphinx-quickstart on Mon Nov 18 09:12:08 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

airspeed velocity
=================

**airspeed velocity** (``asv``) is a tool for benchmarking Python
packages over their lifetime.

It is primarily is designed to benchmark a single project over its
lifetime using a given suite of benchmarks.  The results are displayed
in an interactive web frontend that requires only a basic static
webserver to host.

See an `example airspeed velocity site <http://mdboom.github.io/astropy-benchmark/>`__.

License: `BSD three-clause license
<http://opensource.org/licenses/BSD-3-Clause>`__.

.. warning::

   airspeed velocity is pre-release software.  It is most certainly
   going to change without notice, and may eat kittens.

.. toctree::
   :maxdepth: 1

   installing.rst
   using.rst
   writing_benchmarks.rst
   reference.rst
