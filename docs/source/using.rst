Using airspeed velocity
=======================

**airspeed velocity** is designed to benchmark a single project over
its lifetime using a given set of benchmarks.  Therefore, below, we
use the phrase "project" to refer to the project being benchmarked,
and "benchmark suite" to refer to the set of benchmarks -- i.e.,
little snippets of code that are timed -- being run against the
project.  The benchmark suite may live inside the project's repository,
or it may reside in a separate repository -- the choice is up to you
and is primarily a matter of style or policy.

The user interacts with **airspeed velocity** through the ``asv``
command.  Like ``git``, the ``asv`` command has a number of
``subcommands`` for performing various actions on your benchmarking
project.

Setting up a new benchmarking project
-------------------------------------

The first thing to do is to set up a benchmark suite for **airspeed
velocity**.  It must contain, at a minimum, a single configuration
file, ``asv.conf.json``, and a directory tree of Python files
containing benchmarks.

The `asv quickstart` command can be used to create a new benchmarking
suite.  Change to the directory where you would like your new
benchmarking suite to be created and run::

    $ asv quickstart
    Edit asv.conf.json to get started.

Now that you have the bare bones of a benchmarking suite, the first
thing to do is to edit the configuration file, ``asv.conf.json``.
Open it in your favorite editor.  Like most files that **airspeed
velocity** uses and generates, it is a JSON file.

There are comments in the file describing what each of the elements
do, and there is also a :ref:`conf-reference` with more details.  The
values that will most likely need to be changed for any benchmarking
suite are:

   - ``project``: The name of the project being benchmarked

   - ``project_url``: The project's homepage

   - ``repo``: The URL to the DVCS repository for the project

   - ``show_commit_url``: The base of URLs used to display commits for
     the project

The rest of the values may be often be left to their defaults, unless
testing in multiple versions of Python or against multiple versions of
third-party dependencies is a requirement.

Once you've set up the project's configuration, you'll need to write
some benchmarks.  The benchmarks live in Python files in the
``benchmarks`` directory.  The ``quickstart`` command has created a
single example benchmark already in ``benchmarks/benchmarks.py``::

  class TestIteration(unittest.TestCase):
      """
      An example benchmark that times the performance of various kinds
      of iterating over dictionaries in Python.
      """
      def setUp(self):
          self.d = {}
          for x in range(500):
              self.d[x] = None

      def test_keys(self):
          for key in self.d.keys():
              pass

      def test_iterkeys(self):
          for key in self.d.iterkeys():
              pass

      def test_range(self):
          d = self.d
          for key in range(500):
              x = d[key]

      def test_xrange(self):
          d = self.d
          for key in xrange(500):
              x = d[key]

See :ref:`writing-benchmarks` for more information.

Running benchmarks
------------------

Benchmarks are run using the ``asv run`` subcommand.

Machine information
```````````````````

If this is the first time using ``asv run`` on a given machine, you
will be prompted for information about the machine, such as its
platform, cpu and memory.  **airspeed velocity** will try to make
reasonable guesses, so it's usually ok to just press Enter to accept
each default value.  This information is stored in the
`.asv-machine.json` file in your home directory::

    No ASV machine info file found.
    I will now ask you some questions about this machine to identify
    it in the benchmarks.

    1. NAME: A unique name to identify this machine in the results.
    NAME [cheetah]:
    2. OS: The OS type and version of this machine.
    OS [Linux 3.11.7-200.fc19.x86_64]:
    3. ARCH: The architecture of the machine, e.g. i386
    ARCH [x86_64]:
    4. CPU: A human-readable description of the CPU.
    CPU [Intel(R) Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)]:
    4. RAM: The amount of physical RAM in the system.
    RAM [8.2G]:

Environments
````````````

Next, the Python virtual environments will be set up: one for each of
the combinations of Python versions and the matrix of project
dependencies, if any.  The first time this is run, this may take some
time, as many files are copied over and dependencies are installed
into the environment.  The environments are stored in the ``env``
directory so that the next time the benchmarks are run, things will
start much faster.

Benchmarking
````````````

Finally, the benchmarks are run::

    Benchmarking py2.7
     project commit hash 24ce4372:.
      Uninstalling project..
      Installing /home/mdboom/Work/tmp/asv/project.......
       [25.00%] test_benchmarks.TestIteration.test_iterkeys: 73.81μs
       [50.00%] test_benchmarks.TestIteration.test_keys: 74.04μs
       [75.00%] test_benchmarks.TestIteration.test_range: 97.44μs
       [100.00%] test_benchmarks.TestIteration.test_xrange: 94.76μs

Since we ran ``asv run`` without any arguments, only the current
``master`` branch of the project was benchmarked.  The killer feature
of **airspeed velocity** is that it can track the benchmark
performance of your project over time.  By using the ``--range``
argument, we can specify a range of commits that should be
benchmarked.  The value of this argument is passed directly to ``git
log`` to get the set of commits, so it actually has a very powerful
syntax defined on the `gitrevisions mangpage
<https://www.kernel.org/pub/software/scm/git/docs/gitrevisions.html>`__.

.. note::

    Yes, this is git-specific for now.  Support for Mercurial or other
    DVCSes should be possible in the future.

For example, to benchmark all of the commits since a particular tag
(``v0.1``)::

    asv run --range=v0.1..master

In many cases, this may result in more commits than you are able to
benchmark in a reasonable amount of time.  In that case, the
``--steps`` argument may be helpful.  It specifies the maximum number
of commits you want to test, and it will evenly space them over the
range specified by ``--range``.

The results are stored as a tree of files in the directory
``results/$MACHINE``, where ``$MACHINE`` is the unique machine name
that was set up in your ``.asv-machine`` file.  In order to combine
results from multiple machines, the normal workflow is to commit these
results to a source code repository alongside the results from other
machines.  These results are then collated and "published" altogether
into a single interactive website for viewing.

You can also continue to generate benchmark results for other commits,
or for new benchmarks and continue to throw them in the ``results``
directory.  **airspeed velocity** is designed from the ground up to
handle missing data where certain benchmarks have yet to be performed
-- it's entirely up to you how often you want to generate results, and
on which commits and in which configurations.

Viewing the results
-------------------

To collate a set of results into a viewable website, run::

    asv publish

This will put a tree of files in the ``html`` directory.  This website
can not be viewed directly from the local filesystem, since web
browsers to not support AJAX requests to the local filesystem.
Instead, **airspeed velocity** provides a simple static webserver that
can be used to preview the website.  Just run::

    asv preview

and open the URL that is displayed at the console.  Press Ctrl+C to
stop serving.

To share the website on the open internet, simply put these files on
any webserver that can serve static content.  Github Pages works quite
well, for example.

Managing the results database
-----------------------------

TODO
