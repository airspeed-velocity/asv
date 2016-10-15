.. _writing-benchmarks:

Writing benchmarks
==================

Benchmarks are stored in a collection of ``.py`` files in the
benchmark suite's ``benchmark`` directory (as defined by
``benchmark_dir`` in the ``asv.conf.json`` file).  They may be
arbitrarily nested in subdirectories, and all ``.py`` files will be
used, regardless of their file name.

Within each ``.py`` file, each benchmark is a function or method.  The
name of the functon must have a special prefix, depending on the type
of benchmark.  ``asv`` understands how to handle the prefix in either
``CamelCase`` or lowercase with underscores.  For example, to create a
timing benchmark, the following are equivalent::

    def time_range():
        for i in range(1000):
            pass

    def TimeRange():
        for i in range(1000):
            pass

Benchmarks may be organized into methods of classes if desired::

    class Suite:
        def time_range(self):
            for i in range(1000):
                pass

        def time_xrange(self):
            for i in xrange(1000):
                pass

Running benchmarks during development
-------------------------------------

There are some options to ``asv run`` that may be useful when writing
benchmarks.

You may find that ``asv run`` spends a lot of time setting up the
environment each time.  You can have ``asv run`` use an existing
Python environment that already has the benchmarked project and all of
its dependencies installed.  Use the ``--python`` argument to specify
a Python environment to use::

       asv run --python=python

If you don't care about getting accurate timings, but just want to
ensure the code is running, you can add the ``--quick`` argument,
which will run each benchmark only once::

       asv run --quick

In order to display the standard error output (this includes exception tracebacks)
that your benchmarks may produce, pass the ``--show-stderr`` flag::

       asv run --show-stderr

Finally, there is a special command, ``asv dev``, that uses all of
these features and is equivalent to::

       asv run --python=same --quick --show-stderr --dry-run

Setup and teardown functions
----------------------------

If initialization needs to be performed that should not be included in
the timing of the benchmark, include that code in a ``setup`` method
on the class, or add an attribute called ``setup`` to a free function.

For example::

    class Suite:
        def setup(self):
            # load data from a file
            with open("/usr/share/words.txt", "r") as fd:
                self.words = fd.readlines()

        def time_upper(self):
            for word in self.words:
                word.upper()

    # or equivalently...

    words = []
    def my_setup():
        global words
        with open("/usr/share/words.txt", "r") as fd:
            words = fd.readlines()

    def time_upper():
        for word in words:
            word.upper()
    time_upper.setup = my_setup

You can also include a module-level ``setup`` function, which will be
run for every benchmark within the module, prior to any ``setup``
assigned specifically to each function.

Similarly, benchmarks can also have a ``teardown`` function that is
run after the benchmark.  This is useful if, for example, you need to
clean up any changes made to the filesystem.

Note that although different benchmarks run in separate processes, for
a given benchmark repeated measurement (cf. ``repeat`` attribute) and
profiling occur within the same process.  For these cases, the setup
and teardown routines are run multiple times in the same process.

If ``setup`` raises a ``NotImplementedError``, the benchmark is marked
as skipped.

The ``setup`` method is run multiple times, for each benchmark and for
each repeat.  If the ``setup`` is especially expensive, the
``setup_cache`` method may be used instead, which only performs the
setup calculation once and then caches the result to disk.  It is run
only once also for repeated benchmarks and profiling, unlike
``setup``.  ``setup_cache`` can persist the data for the benchmarks it
applies to in two ways:

   - Returning a data structure, which ``asv`` pickles to disk, and
     then loads and passes it as the first argument to each benchmark.

   - Saving files to the current working directory (which is a
     temporary directory managed by ``asv``) which are then explicitly
     loaded in each benchmark process.  It is probably best to load
     the data in a ``setup`` method so the loading time is not
     included in the timing of the benchmark.

A separate cache is used for each environment and each commit of the
project begin tested and is thrown out between benchmark runs.

For example, caching data in a pickle::

    class Suite:
        def setup_cache(self):
            fib = [1, 1]
            for i in range(100):
                fib.append(fib[-2] + fib[-1])
            return fib

        def track_fib(self, fib):
            return fib[-1]

As another example, explicitly saving data in a file::

    class Suite:
        def setup_cache(self):
            with open("test.dat", "wb") as fd:
                for i in range(100):
                    fd.write('{0}\n'.format(i))

        def setup(self):
            with open("test.dat", "rb") as fd:
                self.data = [int(x) for x in fd.readlines()]

        def track_numbers(self):
            return len(self.data)

The ``setup_cache`` timeout can be specified by setting the
``.timeout`` attribute of the ``setup_cache`` function. The default
value is the maximum of the timeouts of the benchmarks using it.

.. _benchmark-attributes:

Benchmark attributes
--------------------

Each benchmark can have a number of arbitrary attributes assigned to
it.  The attributes that ``asv`` understands depends on the type of
benchmark and are defined below.  For free functions, just assign the
attribute to the function.  For methods, include the attribute at the
class level.  For example, the following are equivalent::

    def time_range():
        for i in range(1000):
            pass
    time_range.timeout = 120.0

    class Suite:
        timeout = 120.0

        def time_range(self):
            for i in range(1000):
                pass

The following attributes are applicable to all benchmark types:

- ``timeout``: The amount of time, in seconds, to give the benchmark
  to run before forcibly killing it.  Defaults to 60 seconds.

- ``pretty_name``: If given, used to display the benchmark name instead of the
  benchmark function name.

Parameterized benchmarks
------------------------

You might want to run a single benchmark for multiple values of some
parameter. This can be done by adding a ``params`` attribute to the
benchmark object::

    def time_range(n):
       for i in range(n):
           pass
    time_range.params = [0, 10, 20, 30]

This will also make the setup and teardown functions parameterized::

    class Suite:
        params = [0, 10, 20]

        def setup(self, n):
            self.obj = range(n)

        def teardown(self, n):
            del self.obj

        def time_range_iter(self, n):
            for i in self.obj:
                pass

If ``setup`` raises a ``NotImplementedError``, the benchmark is marked
as skipped for the parameter values in question.

The parameter values can be any Python objects. However, it is often
best to use only strings or numbers, because these have simple
unambiguous text representations.

When you have multiple parameters, the test is run for all
of their combinations::

     def time_ranges(n, func_name):
         f = {'range': range, 'arange': numpy.arange}[func_name]
         for i in f(n):
             pass

     time_ranges.params = ([10, 1000], ['range', 'arange'])

The test will be run for parameters ``(10, 'range'), (10, 'arange'),
(1000, 'range'), (1000, 'arange')``.

You can also provide informative names for the parameters::

     time_ranges.param_names = ['n', 'function']

These will appear in the test output; if not provided you get default
names such as "param1", "param2".

Note that ``setup_cache`` is not parameterized.

Benchmark types
---------------

Timing
``````

Timing benchmarks have the prefix ``time``.

The timing itself is based on the Python standard library's `timeit`
module, with some extensions for automatic heuristics shamelessly
stolen from IPython's `%timeit
<http://ipython.org/ipython-doc/dev/api/generated/IPython.core.magics.execution.html?highlight=timeit#IPython.core.magics.execution.ExecutionMagics.timeit>`__
magic function.  This means that in most cases the benchmark function
itself will be run many times to achieve accurate timing.

The default timing function is the POSIX ``CLOCK_PROCESS_CPUTIME``,
which measures the CPU time used only by the current process.  This is
available as ``time.process_time`` in Python 3.3 and later, but a
backport is included with ``asv`` for earlier versions of Python.

.. note::

   One consequence of using ``CLOCK_PROCESS_CPUTIME`` is that the time
   spent in child processes of the benchmark is not included.  If your
   benchmark spawns other processes, you may get more accurate results
   by setting the ``timer`` attribute on the benchmark to
   `timeit.default_timer`.

For best results, the benchmark function should contain as little as
possible, with as much extraneous setup moved to a ``setup`` function::

    class Suite:
        def setup(self):
            # load data from a file
            with open("/usr/share/words.txt", "r") as fd:
                self.words = fd.readlines()

        def time_upper(self):
            for word in self.words:
                word.upper()

How ``setup`` and ``teardown`` behave for timing benchmarks
is similar to the Python ``timeit`` module, and the behavior is controlled
by the ``number`` and ``repeat`` attributes, as explained below.

**Attributes**:

- ``goal_time``: ``asv`` will automatically select the number of
  iterations to run the benchmark so that it takes between
  ``goal_time / 10`` and ``goal_time`` seconds each time.  If not
  specified, ``goal_time`` defaults to 2 seconds.

- ``number``: Manually choose the number of iterations.  If ``number``
  is specified, ``goal_time`` is ignored.
  Note that ``setup`` and ``teardown`` are not run between iterations:
  ``setup`` runs first, then the timing routine is called ``number`` times,
  and after that ``teardown`` runs.

- ``repeat``: The number of times to repeat the benchmark, with each
  repetition running the benchmark ``number`` of times.  The minimum
  time from all of these repetitions is used as the final result.
  When not provided, defaults to ``timeit.default_repeat`` (3).
  Setup and teardown are run on each repeat.

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

The ``goal_time``, ``number``, ``repeat``, and ``timer`` attributes
can be adjusted in the ``setup()`` routine, which can be useful for
parameterized benchmarks.

Memory
``````

Memory benchmarks have the prefix ``mem``.

Memory benchmarks track the size of Python objects.  To write a memory
benchmark, write a function that returns the object you want to track::

    def mem_list():
        return [0] * 256

The `asizeof <http://pythonhosted.org/Pympler/asizeof.html>`__ module
is used to determine the size of Python objects.  Since ``asizeof``
includes the memory of all of an object's dependencies (including the
modules in which their classes are defined), a memory benchmark
instead calculates the incremental memory of a copy of the object,
which in most cases is probably a more useful indicator of how much
space *each additional* object will use.  If you need to do something
more specific, a generic :ref:`tracking` benchmark can be used
instead.

.. note::

    The memory benchmarking feature is still experimental.
    ``asizeof`` may not be the most appropriate metric to use.

.. note::

    The memory benchmarks are not supported on PyPy.

.. _peak-memory:

Peak Memory
```````````

Peak memory benchmarks have the prefix ``peakmem``.

Peak memory benchmark tracks the maximum resident size (in bytes) of
the process in memory. This does not necessarily count memory paged
on-disk, or that used by memory-mapped files.  To write a peak memory
benchmark, write a function that does the operation whose maximum
memory usage you want to track::

    def peakmem_list():
        [0] * 165536


.. note::

   The peak memory benchmark also counts memory usage during the
   ``setup`` routine, which may confound the benchmark results. One
   way to avoid this is to use ``setup_cache`` instead.


.. _tracking:

Tracking (Generic)
``````````````````

It is also possible to use ``asv`` to track any arbitrary numerical
value.  "Tracking" benchmarks can be used for this purpose and use the
prefix ``track``.  These functions simply need to return a numeric
value.  For example, to track the number of objects known to the
garbage collector at a given state::

    import gc

    def track_num_objects():
        return len(gc.get_objects())
    track_num_objects.unit = "objects"

**Attributes**:

- ``unit``: The unit of the values returned by the benchmark.  Used
  for display in the web interface.
