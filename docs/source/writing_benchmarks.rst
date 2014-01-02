.. _writing-benchmarks:

Writing benchmarks
==================

Benchmarks are stored in a collection of ``.py`` files in the
benchmarking projects benchmark directory (as defined by
``benchmark_dir`` in the ``asv.conf.json`` file).  They may be
arbitrarily nested in subdirectories, and all ``.py`` files will be
used, regardless of their file name.

Within each ``.py`` file, each benchmark in a function or method.  The
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

The following attributes are applicable to all benchmark types::

    - ``timeout``: The amount of time, in seconds, to give the
      benchmark to run before forcibly killing it.  Defaults to 60
      seconds.

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
  When not provided, defaults to `timeit.default_repeat` (3).

- ``timer``: The timing function to use, which can be any source of
  monotonically increasing numbers, such as `time.clock` or
  `time.time`.  If not provided, defaults to `timeit.default_timer`.

  On Windows, `time.clock` has microsecond granularity, but
  `time.time`'s granularity is 1/60th of a second. On Unix,
  `time.clock` has 1/100th of a second granularity, and `time.time` is
  much more precise. On either platform, `timeit.default_timer`
  measures wall clock time, not the CPU time. This means that other
  processes running on the same computer may interfere with the
  timing.

Memory
``````

Memory benchmarks have the prefix ``mem``.

Memory benchmarks track the size of Python objects.  To write a memory
benchmark, write a function that returns the object you want to track::

    def mem_list():
        return [0] * 256

The `asizeof <http://pythonhosted.org/Pympler/asizeof.html>`__ module
is used to determine the size of Python objects.  If you need to do
something fancier, a generic :ref:`tracking` benchmark could be used
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
  for display in the web interface.b
