.. _writing-benchmarks:

Writing benchmarks
==================

Benchmarks are discovered and run with the help of the standard
library's ``unittest`` module.

.. note::

    As this approach has a lot of shortcomings (though it was
    convenient to get up and running quickly), I'm not going to spend
    a whole lot of time documenting it now.  It will likely be
    completely overhauled and replaced.

Timing
------

The number of iterations that a benchmark is run is determined
automatically using a heuristic shamelessly stolen from IPython's
``timeit`` magic function.

It adjusts the iterations so that a single "repetition" of the
benchmark takes between 0.2 and 2.0 seconds.  If a single benchmark
iteration takes more than 2.0 seconds, it will be run once per
repetition.
