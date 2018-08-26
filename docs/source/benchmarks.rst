Benchmark types and attributes
==============================

.. contents::

Benchmark attributes can either be applied directly to the benchmark function::

    def time_something():
        pass
  
    time_something.timeout = 123

or appear as class attributes::

    class SomeBenchmarks(object):
        timeout = 123

        def time_something(self):
            pass

Benchmark types
---------------

The following benchmark types are recognized:

- ``def time_*()``: measure time taken by the function. See :ref:`timing-benchmarks`.
- ``def mem_*()``: measure memory size of the object returned.  See :ref:`memory-benchmarks`.
- ``def peakmem_*()``: measure peak memory size of the process when calling the function.
  See :ref:`peak-memory`.
- ``def track_*()``: use the returned numerical value as the benchmark result
  See :ref:`tracking`.


Benchmark attributes
--------------------

General
```````

The following attributes are applicable to all benchmark types:

- ``timeout``: The amount of time, in seconds, to give the benchmark
  to run before forcibly killing it.  Defaults to 60 seconds.

- ``benchmark_name``: If given, used as benchmark function name instead of generated one
  ``<module>.<class>.<function>``.

- ``pretty_name``: If given, used to display the benchmark name instead of the
  benchmark function name.

- ``version``: Used to determine when to invalidate old benchmark
  results.  Benchmark results produced with a different value of the
  version than the current value will be ignored.  The value can be
  any Python string (or other object, ``str()`` will be taken).

  Default (if ``version=None`` or not given): hash of the source code
  of the benchmark function and setup and setup_cache methods. If the
  source code of any of these changes, old results become invalidated.

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


Timing benchmarks
`````````````````

- ``warmup_time``: ``asv`` will spend this time (in seconds) in calling
  the benchmarked function repeatedly, before starting to run the actual
  benchmark. If not specified, ``warmup_time`` defaults to 0.1 seconds
  (on PyPy, the default is 1.0 sec).

- ``processes``: How many processes to launch for running the benchmarks
  (default: 2). The processes run benchmarks in an interleaved order,
  allowing to sample over longer periods of background performance
  variations (e.g. CPU power levels).

- ``repeat``: The number measurement samples to collect per process.
  Each sample consists of running the benchmark ``number`` times.
  The median time from all samples is used as the final measurement
  result.

  ``repeat`` can be a tuple ``(min_repeat, max_repeat, max_time)``.
  In this case, the measurement first collects at least ``min_repeat``
  samples, and continues until either ``max_repeat`` samples are collected
  or the collection time exceeds ``max_time``.

  When not provided (``repeat`` set to 0), the default value is
  ``(1, 10, 20.0)`` if ``processes==1`` and ``(1, 5, 10.0)`` otherwise.

- ``number``: Manually choose the number of iterations in each sample.
  If ``number`` is specified, ``sample_time`` is ignored.
  Note that ``setup`` and ``teardown`` are not run between iterations:
  ``setup`` runs first, then the timed benchmark routine is called
  ``number`` times, and after that ``teardown`` runs.

- ``sample_time``: ``asv`` will automatically select ``number`` so that
  each sample takes approximatively ``sample_time`` seconds.  If not
  specified, ``sample_time`` defaults to 10 milliseconds.

- ``min_run_count``: the function is run at least this many times during
  benchmark. Default: 2

- ``timer``: The timing function to use, which can be any source of
  monotonically increasing numbers, such as `time.clock`, `time.time`
  or ``time.process_time``.  If it's not provided, it defaults to
  ``time.process_time`` (or a backported version of it for versions of
  Python prior to 3.3), but other useful values are
  `timeit.default_timer` to use the default ``timeit`` behavior on
  your version of Python.

  On Windows, `time.clock` has microsecond granularity, but
  `time.time`'s granularity is 1/60th of a second. On Unix,
  `time.clock` has 1/100th of a second granularity, and `time.time` is
  much more precise. On either platform, `timeit.default_timer`
  measures wall clock time, not the CPU time. This means that other
  processes running on the same computer may interfere with the
  timing.  That's why the default of ``time.process_time``, which only
  measures the time used by the current process, is often the best
  choice.

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
