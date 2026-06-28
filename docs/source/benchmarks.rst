Benchmark types and attributes
==============================

.. only:: not man

   .. contents::

.. warning::

   .. versionchanged:: 0.6.0

      The code for these have now been moved to be in ``asv_runner``, and the
      rest of the documentation may be outdated.

Benchmark types
---------------

The following benchmark types are recognized:

- ``def time_*()``: measure time taken by the function. See :ref:`timing-benchmarks`.
- ``def timeraw_*()``: measure time taken by the function, after interpreter start. See :ref:`raw-timing-benchmarks`.
- ``def mem_*()``: measure memory size of the object returned.  See :ref:`memory-benchmarks`.
- ``def peakmem_*()``: measure peak memory size of the process when calling the function.
  See :ref:`peak-memory`.
- ``def track_*()``: use the returned numerical value as the benchmark result
  See :ref:`tracking`.

.. note::

   .. versionadded:: 0.6.2

        External benchmarks may be defined through ``asv_runner`` and a list of
        benchmark plugins (like ``asv_bench_memray``) may be found here, with
        samples at `asv_samples
        <https://github.com/airspeed-velocity/asv_samples>`_.

Benchmark attributes
--------------------

Benchmark attributes can either be applied directly to the benchmark function::

    def time_something():
        pass

    time_something.timeout = 123

or appear as class attributes::

    class SomeBenchmarks:
        timeout = 123

        def time_something(self):
            pass

Different benchmark types have their own sets of applicable
attributes.  Moreover, the following attributes are applicable to all
benchmark types:

- ``timeout``: The amount of time, in seconds, to give the benchmark
  to run before forcibly killing it.  Defaults to 60 seconds.

- ``benchmark_name``: If given, used as benchmark function name instead of generated one
  ``<module>.<class>.<function>``.

- ``pretty_name``: If given, used to display the benchmark name instead of the
  benchmark function name.

- ``pretty_source``: If given, used to display a custom version of the benchmark source.

- ``version``: **Benchmark suite version** for this benchmark only (not
  the project's release version and not the results-file API version).
  Used to invalidate old measurements when the benchmark definition
  changes.  Results recorded with a different ``version`` than the
  current suite are ignored in compare/publish.  The value can be any
  Python string (or other object; ``str()`` is taken).

  Default (if ``version=None`` or not given): hash of the source code
  of the benchmark function and setup and setup_cache methods. If the
  source code of any of these changes, old results become invalidated.
  See also the note under :ref:`comparing` in :doc:`using`.

- ``setup``: function to be called as a setup function for the benchmark
  See :ref:`setup-and-teardown` for discussion.

- ``teardown``: function to be called as a teardown function for the benchmark
  See :ref:`setup-and-teardown` for discussion.

- ``setup_cache``: function to be called as a cache setup function.
  See :ref:`setup-and-teardown` for discussion.

- ``param_names``: list of parameter names
  See :ref:`parametrized-benchmarks` for discussion.

- ``params``: list of lists of parameter values.
  If there is only a single parameter, may also be a list of parameter values.
  See :ref:`parametrized-benchmarks` for discussion.

  Example::

     def setup_func(n, func):
         print(n, func)

     def teardown_func(n, func):
         print(n, func)

     def time_ranges(n, func):
         for i in func(n):
             pass

     time_ranges.setup = setup_func
     time_ranges.param_names = ['n', 'func']
     time_ranges.params = ([10, 1000], [range, numpy.arange])

  The benchmark will be run for parameters ``(10, range), (10,
  numpy.arange), (1000, range), (1000, numpy.arange)``. The setup and
  teardown functions will also obtain these parameters.

  Note that ``setup_cache`` is not parameterized.

  For the purposes of identifying benchmarks in the UI, ``repr()`` is called
  on the elements of ``params``. In the event these strings contain memory
  addresses, those addresses are stripped to allow comparison across runs.
  Additionally, if this results in a non-unique mapping, each duplicated
  element will be suffixed with a distinct integer identifier corresponding
  to order of appearance.

Timing benchmarks
`````````````````

- ``warmup_time``: After the benchmark process starts (and after ``number``
  is calibrated when applicable), ``asv`` spends this many **seconds**
  calling the benchmarked function repeatedly **before** recorded samples.
  Default is 0.1 seconds (1.0 on PyPy).  Warmup is per benchmark process,
  not a separate outer loop over the whole suite.

- ``rounds``: How many **interleaved rounds** to run this timing benchmark
  in (default: 2).  In each round, ASV runs through the selected benchmarks
  (with other timing benchmarks interleaved) so measurements span longer
  periods of background variation (for example CPU power levels).  With a
  single benchmark selected (``asv run -b …``), you still get ``rounds``
  passes over that benchmark; you will not necessarily see ``rounds`` as a
  separate user-visible "loop counter" in the UI.

- ``repeat``: How many **measurement samples** to collect **per round**.
  Each sample runs the benchmark function ``number`` times (see below);
  ``setup`` / ``teardown`` run around each sample, not around each inner
  iteration.  The median over samples (across rounds) is the reported time.

  ``repeat`` can be a tuple ``(min_repeat, max_repeat, max_time)``.
  ASV collects at least ``min_repeat`` samples, then continues until
  ``max_repeat`` samples or about ``max_time`` seconds of sampling, whichever
  comes first.

  When not provided (``repeat`` set to 0), the default is
  ``(1, 10, 20.0)`` if ``rounds==1`` and ``(1, 5, 10.0)`` otherwise.

- ``number``: Inner iterations **per sample** (timed together, then divided
  by ``number``).  If set manually, ``sample_time`` is ignored.
  ``setup`` runs once per sample, then the function is called ``number``
  times, then ``teardown``.

- ``sample_time``: Target duration **in seconds** for one sample (default
  0.01, i.e. 10 ms).  When ``number`` is not set, ASV **calibrates**
  ``number`` once in the benchmark process so that running the function
  ``number`` times takes about ``sample_time`` seconds, then collects
  samples with that ``number``.  Calibration runs are not the reported
  result; they only choose ``number``.

- ``min_run_count``: Ensure the benchmark function body runs at least this
  many times in total during the timing protocol (default: 2).  This is a
  **floor on total invocations**, distinct from ``repeat``'s
  ``min_repeat`` (minimum **samples** per round).  Use ``min_run_count``
  when you need a minimum amount of work even if ``number`` calibration
  would otherwise stay very small; use ``repeat`` / ``min_repeat`` to
  control how many timed samples feed the median.

- ``timer``: The timing function to use, which can be any source of
  monotonically increasing numbers, such as ``time.clock``, ``time.time``
  or ``time.process_time``.  If it's not provided, it defaults to
  ``timeit.default_timer``, but other useful values are
  ``process_time``, for which ``asv`` provides a backported version for
  versions of Python prior to 3.3.

  .. versionchanged:: 0.4

     Previously, the default timer measured process time, which was chosen
     to minimize noise from other processes. However, on Windows, this is
     only available at a resolution of 15.6ms, which is greater than the
     recommended benchmark runtime of 10ms. Therefore, we default to the
     highest resolution clock on any platform.

The ``sample_time``, ``number``, ``repeat``, and ``timer`` attributes
can be adjusted in the ``setup()`` routine, which can be useful for
parameterized benchmarks.


Tracking benchmarks
```````````````````

- ``unit``: The unit of the values returned by the benchmark.  Used
  for display in the web interface.


Environment variables
---------------------

When ``asv`` runs benchmarks, several environment variables are
defined, see :doc:`env_vars`.
