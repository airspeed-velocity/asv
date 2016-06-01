Developer Docs
==============

This section describes some things that may be of interest to
developers of ``asv``.

.. contents::

Benchmark suite layout
----------------------

A benchmark suite directory has the following layout.  The
``$``-prefixed variables refer to values in the ``asv.conf.json`` file.

- ``asv.conf.json``: The configuration file.

- ``$benchmark_dir``: Contains the benchmark code, created by the
  user.  Each subdirectory needs an ``__init__.py``.

- ``$project/``: A clone of the project being benchmarked.
  Information about the history is grabbed from here, but the actual
  building happens in the environment-specific clones described below.

- ``$env_dir/``: Contains the environments used for building and
  benchmarking.  There is one environment in here for each specific
  combination of Python version and library dependency.  Generally,
  the dependencies are only installed once, and then reused on
  subsequent runs of ``asv``, but the project itself needs to be
  rebuilt for each commit being benchmarked.

  - ``$ENVIRONMENT_HASH/``: The directory name of each environment is
    the md5hash of the list of dependencies and the Python version.
    This is not very user friendly, but this keeps the filename within
    reasonable limits.

    - ``asv-env-info.json``: Contains information about the
      environment, mainly the Python version and dependencies used.

    - ``project/``: An environment-specific clone of the project
      repository.  Each environment has its own clone so that builds
      can be run in parallel without fear of clobbering (particularly
      for projects that generate source files outside of the
      ``build/`` directory.  These clones are created from the main
      ``$project/`` directory using the ``--shared`` option to ``git
      clone`` so that the repository history is stored in one place to
      save on disk space.

      The project is built in this directory with the standard
      ``distutils`` ``python setup.py build`` command.  This means
      repeated builds happen in the same place and `ccache
      <https://ccache.samba.org>`__ is able to cache and reuse many of
      the build products.

    - ``wheels/``: If ``wheel_cache_size`` in ``asv.conf.json`` is set
      to something other than 0, this contains `Wheels
      <https://pypi.python.org/pypi/wheel>`__ of the last N project
      builds for this environment.  In this way, if a build for a
      particular commit has already been performed and cached, it can
      be restored much more quickly.  Each subdirectory is a commit
      hash, containing one ``.whl`` file and a timestamp.

    - ``usr/``, ``lib/``, ``bin/`` etc.: These are the virtualenv or
      Conda environment directories that we install the project into
      and then run benchmarks from.

- ``$results_dir/``: This is the "database" of results from benchmark
  runs.

  - ``benchmarks.json``: Contains metadata about all of the
    benchmarks in the suite.  It is a dictionary from benchmark
    names (a fully-qualified dot-separated path) to dictionaries
    containing information about that benchmark.  Useful keys
    include:

    - ``code``: The Python code of the benchmark

    - ``params``: List of lists describing parameter values of a
      parameterized benchmark. If benchmark is not parameterized, an
      empty list. Otherwise, the n-th entry of the list is a list of
      the Python ``repr()`` strings for the values the n-th parameter
      should loop over.

    - ``param_names``: Names for parameters for a parameterized
      benchmark. Must be of the same length as the ``params`` list.

    Other keys are specific to the kind of benchmark, and correspond
    to :ref:`benchmark-attributes`.

  - ``MACHINE/``: Within the results directory is a directory for each
    machine.  Putting results from different machines in separate
    directories makes the results trivial to merge, which is useful
    when benchmarking across different platforms or architectures.

    - ``HASH-pythonX.X-depA-depB.json``: Each JSON file within a
      particular machine represents a run of benchmarks for a
      particular project commit in a particular environment.  Useful
      keys include:

      - ``commit_hash``: The project commit that the benchmarks were
        run on.

      - ``date``: A Javascript date stamp of the date of the commit
        (not when the benchmarks were run).

      - ``params``: Information about the machine the benchmarks were
        run on.

      - ``results``: A dictionary from benchmark names to benchmark
        results.

        - If non-parameterized benchmark, the result is a single value.

        - For parameterized benchmarks, the result is a dictionary
          with keys ``params`` and ``result``. The ``params`` value
          contains a copy of the parameter values of the benchmark, as
          described above. If the user has modified the benchmark
          after the benchmark was run, these may differ from the
          current values. The ``result`` value is a list of
          results. Each entry corresponds to one combination of the
          parameter values. The n-th entry in the list corresponds to
          the parameter combination ``itertools.product(*params)[n]``,
          i.e., the results appear in cartesian product order, with
          the last parameters varying fastest.

        - In the results, ``null`` indicates a failed benchmark,
          including failures in installing the project version. ``NaN``
          indicates a benchmark explicitly skipped by the benchmark suite.

      - ``started_at``: A dictionary from benchmark names to Javascript
        time stamps indicating the start time of the benchmark run.

      - ``ended_at``: A dictionary from benchmark names to Javascript
        time stamps indicating the end time of the benchmark run.

- ``$html_dir/``: The output of ``asv publish``, that turns the raw
  results in ``$results_dir/`` into something viewable in a web
  browser.  It is an important feature of ``asv`` that the results can
  be shared on a static web server, so there is no server side
  component, and the result data is accessed through AJAX calls from
  Javascript.  Most of the files at the root of ``$html_dir/`` are
  completely static and are just copied verbatim from ``asv/www/`` in
  the source tree.

  - ``index.json``: Contains an index into the benchmark data,
    describing what is available.  Important keys include:

    - ``benchmarks``: A dictionary of benchmarks.  At the moment, this
      is identical to the content in ``$results_dir/benchmarks.json``.

    - ``revision_to_hash``: A dictionary mapping revision number to commit
      hash. This allows to show commits tooltip in graph and commits involved
      in a regression.

    - ``revision_to_date``: A dictionary mapping Javascript date stamps to
      revisions (including tags).  This allows the x-scale of a plot to be scaled
      by date.

    - ``machines``: Describes the machines used for testing.

    - ``params``: A dictionary of parameters against which benchmark
      results can be selected.  Each entry is a list of valid values
      for that parameter.

    - ``tags``: A dictionary of git tags and their revisions, so this
      information can be displayed in the plot.

  - ``graphs/``: This is a nested tree of directories where each level
    is a parameter from the ``params`` dictionary, in asciibetical
    order.  The web interface, given a set of parameters that are set,
    get easily grab the associated graph.

    - ``BENCHMARK_NAME.json``: At the leaves of this tree are the
      actual benchmark graphs.  It contains a list of pairs, where
      each pair is of the form ``(timestamp, result_value)``.  For
      parameterized benchmarks, ``result_value`` is a list of results,
      corresponding to ``itertools.product`` iteration over the
      parameter combinations, similarly as in the result files. For
      non-parameterized benchmarks, it is directly the result.
      Missing values (eg. failed and skipped benchmarks) are
      represented by ``null``.


Full-stack testing
------------------

For full-stack testing, we use `Selenium WebDriver
<http://seleniumhq.org/>`__ and its `Python bindings
<https://pypi.python.org/pypi/selenium>`__.
Additional documentation for Selenium Python bindings is `here
<https://selenium-python.readthedocs.org/index.html>`__.

The browser back-end can be selected via::

    python setup.py test -a "--webdriver=PhantomJS"
    py.test --webdriver=PhantomJS

The allowed values include ``PhantomJS`` (default) and ``Chrome``,
corresponding to:

* `PhantomJS <http://phantomjs.org/>`__:
  Headless web browser. Runs without requiring a display.  On
  Ubuntu, install via ``apt-get install phantomjs``.

* `ChromeDriver <https://code.google.com/p/selenium/wiki/ChromeDriver>`__:
  Chrome-based controllable browser. Cannot run without a display,
  and will pop up a window when running. On Ubuntu, install via
  ``apt-get install chromium-chromedriver``.

For other options regarding the webdriver to use, see ``py.test --help``.


Step detection
--------------

.. automodule:: asv.step_detect
