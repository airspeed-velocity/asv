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
on the class, or set add an attribute called ``setup`` to a free
function.  For example::

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
    def setup():
        global words
        with open("/usr/share/words.txt", "r") as fd:
            words = fd.readlines()

    def time_upper():
        for word in words:
            word.upper()
    time_upper.setup = setup

You can also include a module-level ``setup`` function, which will be
run for every benchmark within the module, prior to any ``setup``
assigned specifically to each function.

Similarly, benchmarks can also have a ``teardown`` function that is
run after the benchmark.  This is useful if, for example, you need to
clean up any changes made to the filesystem.  Generally, however, it
is not required: each benchmark runs in its own process, so any
tearing down of in-memory state happens automatically.

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

**Attributes**:

- ``goal_time``: ``asv`` will automatically select the number of
  iterations to run the benchmark so that it takes between
  ``goal_time / 10`` and ``goal_time`` seconds each time.  If not
  specified, ``goal_time`` defaults to 2 seconds.

- ``number``: Manually choose the number of iterations.  If ``number``
  is specified, ``goal_time`` is ignored.

- ``repeat``: The number of times to repeat the benchmark, with each
  repetition running the benchmark ``number`` of times.  The minimum
  time from all of these repetitions is used as the final result.
  When not provided, defaults to ``timeit.default_repeat`` (3).

- ``timer``: The timing function to use, which can be any source of
  monotonically increasing numbers, such as `time.clock`, `time.time`
  or ``time.process_time``.  If it's not provided, it defaults to
  ``time.process_time`` (or a backported version of it for versions of
  Python prior to 3.3), but other useful values are
  `timeit.default_timer` to use the default ``timeit`` behavior on
  your version of Python.  The ``asvtools`` module, which you can
  import from your benchmark suite, contains the aliases
  ``process_time`` and ``wall_time`` which can also be used here.

  On Windows, `time.clock` has microsecond granularity, but
  `time.time`'s granularity is 1/60th of a second. On Unix,
  `time.clock` has 1/100th of a second granularity, and `time.time` is
  much more precise. On either platform, `timeit.default_timer`
  measures wall clock time, not the CPU time. This means that other
  processes running on the same computer may interfere with the
  timing.  That's why the default of ``time.process_time``, which only
  measures the time used by the current process, is often the best
  choice.

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

Multiple
````````

There is also a special benchmark type for benchmarks that you want to
test in multiple ways, for example to test both for memory usage and
run time.  "Multiple" benchmarks use the prefix ``multi`` and have a
required attribute ``types``, which is a list of benchmark types to
run.

**Attributes**:

- ``types``: A list of types to run on the benchmark.  Each entry is a
  2- or 3-length tuple with the following elements:

  - ``name``: The name of the subbenchmark
  - ``type``: The type of benchmark.  Must be a supported benchmark
    prefix, e.g. ``time``, ``mem`` or ``track``.
  - ``args``: A dictionary of attributes for the benchmark.  This can
    be used to override any of the benchmark-type-specific attributes.

Examples
~~~~~~~~

To write a multi benchmark that tests process time, wall clock time
and memory usage::

  import asvtools

  def multi_range():
      range(100000)
  multi_range.types = [
      ('process_time', 'time'),
      ('wall_time', 'time', {'timer': asvtools.wall_time}),
      ('memory', 'mem')
  ]

If you have multiple benchmarks that you want to run in the same way,
you can assign the types to a variable and reuse that::

  import asvtools

  my_types = [
      ('process_time', 'time'),
      ('wall_time', 'time', {'timer': asvtools.wall_time}),
      ('memory', 'mem')
  ]

  def multi_range():
      range(100000)
  multi_range.types = my_types

  def multi_xrange():
      xrange(100000)
  multi_xrange.types = my_types

Or, you can put all of the benchmarks in a suite::

  import asvtools

  class MySuite:
      types = [
          ('process_time', 'time'),
          ('wall_time', 'time', {'timer': asvtools.wall_time}),
          ('memory', 'mem')
      ]

      def multi_range(self):
          range(100000)

      def multi_xrange(self):
          xrange(100000)
