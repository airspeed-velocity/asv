Using airspeed velocity
=======================

**airspeed velocity** is designed to benchmark a single project over
its lifetime using a given set of benchmarks.  Below, we use the
phrase "project" to refer to the project being benchmarked, and
"benchmark suite" to refer to the set of benchmarks -- i.e., little
snippets of code that are timed -- being run against the project.  The
benchmark suite may live inside the project's repository, or it may
reside in a separate repository -- the choice is up to you and is
primarily a matter of style or policy.  Importantly, the result data
stored alongside the benchmark suite may grow quite large, which is a
good reason to not include it in the main project repository.

The user interacts with **airspeed velocity** through the ``asv``
command.  Like ``git``, the ``asv`` command has a number of
"subcommands" for performing various actions on your benchmarking
project.

Setting up a new benchmarking project
-------------------------------------

The first thing to do is to set up an **airspeed velocity** benchmark
suite for your project.  It must contain, at a minimum, a single
configuration file, ``asv.conf.json``, and a directory tree of Python
files containing benchmarks.

The ``asv quickstart`` command can be used to create a new
benchmarking suite.  Change to the directory where you would like your
new benchmarking suite to be created and run::

    $ asv quickstart
    Edit asv.conf.json to get started.

Now that you have the bare bones of a benchmarking suite, let's edit
the configuration file, ``asv.conf.json``.  Like most files that
**airspeed velocity** uses and generates, it is a JSON file.

There are comments in the file describing what each of the elements
do, and there is also a :ref:`conf-reference` with more details.  The
values that will most likely need to be changed for any benchmarking
suite are:

   - ``project``: The name of the project being benchmarked.

   - ``project_url``: The project's homepage.

   - ``repo``: The URL to the DVCS repository for the project.  This
     should be a read-only URL so that anyone, even those without
     commit rights to the repository, can run the benchmarks.  For a
     project on github, for example, the URL would look like:
     ``https://github.com/spacetelescope/asv.git``

   - ``show_commit_url``: The base of URLs used to display commits for
     the project.  This allows users to click on a commit in the web
     interface and have it display the contents of that commit.  For a
     github project, the URL is of the form
     ``http://github.com/$OWNER/$REPO/commit/``.

The rest of the values can usually be left to their defaults, unless
you want to benchmark against multiple versions of Python or multiple
versions of third-party dependencies.

Once you've set up the project's configuration, you'll need to write
some benchmarks.  The benchmarks live in Python files in the
``benchmarks`` directory.  The ``quickstart`` command has created a
single example benchmark file already in
``benchmarks/benchmarks.py``::

    class TimeSuite:
        """
        An example benchmark that times the performance of various kinds
        of iterating over dictionaries in Python.
        """
        def setup(self):
            self.d = {}
            for x in range(500):
                self.d[x] = None

        def time_keys(self):
            for key in self.d.keys():
                pass

        def time_iterkeys(self):
            for key in self.d.iterkeys():
                pass

        def time_range(self):
            d = self.d
            for key in range(500):
                x = d[key]

        def time_xrange(self):
            d = self.d
            for key in xrange(500):
                x = d[key]

You'll want to replace these benchmarks with your own.  See
:ref:`writing-benchmarks` for more information.

Running benchmarks
------------------

Benchmarks are run using the ``asv run`` subcommand.

Let's start by just benchmarking the current ``master`` of the project::

    $ asv run master^!

Machine information
```````````````````

If this is the first time using ``asv run`` on a given machine, (which
it probably is, if you're following along), you will be prompted for
information about the machine, such as its platform, cpu and memory.
**airspeed velocity** will try to make reasonable guesses, so it's
usually ok to just press ``Enter`` to accept each default value.  This
information is stored in the ``.asv-machine.json`` file in your home
directory::

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

.. note::

    If you ever need to update the machine information later, you can
    run `asv machine`.

Environments
````````````

Next, the Python virtual environments will be set up: one for each of
the combinations of Python versions and the matrix of project
dependencies, if any.  The first time this is run, this may take some
time, as many files are copied over and dependencies are installed
into the environment.  The environments are stored in the ``env``
directory so that the next time the benchmarks are run, things will
start much faster.

.. note::

    ``asv`` does not build Pythons for you, but it expects to find
    each of the Python versions specified in the ``asv.conf.json``
    file available on the ``PATH``.  For example, if the
    ``asv.conf.json`` file has::

        "pythons": ["2.7", "3.3"]

    then it will use the executables named ``python2.7`` and
    ``python3.3`` on the path.  There are many ways to get multiple
    versions of Python installed -- your package manager, ``apt-get``,
    ``yum``, ``MacPorts`` or ``homebrew`` probably has them, or you
    can also use `pyenv <https://github.com/yyuu/pyenv>`__.  ``asv``
    always works in a virtual environment, so it will not change what
    is installed in any of the python environments on your system.

Benchmarking
````````````

Finally, the benchmarks are run::

   $ asv run master^!
   Benchmarking py2.7
     project commit hash 24ce4372:.
      Uninstalling project..
      Installing ...asv/project.......
       [25.00%] test_benchmarks.TestIteration.test_iterkeys: 73.81μs
       [50.00%] test_benchmarks.TestIteration.test_keys: 74.04μs
       [75.00%] test_benchmarks.TestIteration.test_range: 97.44μs
       [100.00%] test_benchmarks.TestIteration.test_xrange: 94.76μs

To improve reproducibility, each benchmark is run in its own process.

The killer feature of **airspeed velocity** is that it can track the
benchmark performance of your project over time.  The required
``range`` argument to ``asv run`` specifies a range of commits that
should be benchmarked.  The value of this argument is passed directly
to ``git log`` to get the set of commits, so it actually has a very
powerful syntax defined in the `gitrevisions manpage
<https://www.kernel.org/pub/software/scm/git/docs/gitrevisions.html>`__.

.. note::

    Yes, this is git-specific for now.  Support for Mercurial or other
    DVCSes should be possible in the future, but not at the moment.

For example, to benchmark all of the commits since a particular tag
(``v0.1``)::

    asv run v0.1..master

In many cases, this may result in more commits than you are able to
benchmark in a reasonable amount of time.  In that case, the
``--steps`` argument is helpful.  It specifies the maximum number of
commits you want to test, and it will evenly space them over the
specified range.

You may also want to benchmark every commit that has already been
benchmarked on all the other machines.  For that, use::

    asv run existing

You can benchmark all commits since the last one that was benchmarked
on this machine.  This is useful for running in nightly cron jobs::

    asv run latest

The results are stored as a tree of files in the directory
``results/$MACHINE``, where ``$MACHINE`` is the unique machine name
that was set up in your ``~/.asv-machine.json`` file.  In order to
combine results from multiple machines, the normal workflow is to
commit these results to a source code repository alongside the results
from other machines.  These results are then collated and "published"
altogether into a single interactive website for viewing.

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
browsers do not support AJAX requests to the local filesystem.
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

The ``asv rm`` command can be used to remove benchmarks from the
database.  The command takes an arbitrary number of ``key=value``
entries that are "and"ed together to determine which benchmarks to
remove.

The keys may be one of:

    - ``benchmark``: A benchmark name

    - ``python``: The version of python

    - ``commit_hash``: The commit hash

    - machine-related: ``machine``, ``arch``, ``cpu``, ``os``, ``ram``

    - environment-related: a name of a dependency, e.g. ``numpy``

The values are glob patterns, as supported by the Python standard
library module `fnmatch`.  So, for example, to remove all benchmarks
in the ``time_units`` module::

    asv rm "benchmark=time_units.*"

Note the double quotes around the entry to prevent the shell from
expanding the ``*`` itself.

The ``asv rm`` command will prompt before performing any operations.
Passing the ``-y`` option will skip the prompt.  Note that generally
the results will be stored in a source code repository, so it should
be possible to undo any of the changes using the DVCS directly as
well.

Here is a more complex example, to remove all of the benchmarks on
Python 2.7 and the machine named ``giraffe``::

    asv rm python=2.7 machine=giraffe
