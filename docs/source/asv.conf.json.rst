.. _conf-reference:

``asv.conf.json`` reference
===========================

The ``asv.conf.json`` file contains information about a particular
benchmarking project.  The following describes each of the keys in
this file and their expected values.

``project``
-----------
The name of the project being benchmarked.

``project_url``
---------------
The URL to the homepage of the project.  This can point to anywhere,
really, as it's only used for the link at the top of the benchmark
results page back to your project.

``repo``
--------
The URL to the repository for the project.

The value can also be a path, relative to the location of the
configuration file. For example, if the benchmarks are stored in the
same repository as the project itself, and the configuration file is
located at ``benchmarks/asv.conf.json`` inside the repository, you can
set ``"repo": ".."`` to use the local repository.

Currently, only ``git`` and ``hg`` repositories are supported, so this must be
a URL that ``git`` or ``hg`` know how to clone from, for example:

   - git@github.com:spacetelescope/asv.git

   - https://github.com/spacetelescope/asv.git

   - ssh://hg@bitbucket.org/yt_analysis/yt

   - hg+https://bitbucket.org/yt_analysis/yt

The repository may be readonly.

.. note::

   Currently, mercurial works only on Python 2, although the interface to
   Mercurial used in ``asv`` (``python-hglib``) is being ported to Python 3.
   At the present time, Mercurial support will only function on Python 2.

``branches``
------------
Branches to generate benchmark results for.

This controls how the benchmark results are displayed, and what
benchmarks ``asv run ALL`` and ``asv run NEW`` run.

If not provided, "master" (Git) or "default" (Mercurial) is chosen.

``show_commit_url``
-------------------
The base URL to show information about a particular commit.  The
commit hash will be added to the end of this URL and then opened in a
new tab when a data point is clicked on in the web interface.

For example, if using Github to host your repository, the
``show_commit_url`` should be:

    http://github.com/owner/project/commit/

``pythons``
-----------
The versions of Python to run the benchmarks in.  If not provided, it
will to default to the version of Python that the ``asv`` command
(master) is being run under.

If provided, it should be a list of strings.  It may be one of the
following:

- a Python version string, e.g. ``"2.7"``, in which case:

  - if ``conda`` is found, ``conda`` will be used to create an
    environment for that version of Python

  - if ``virtualenv`` is installed, ``asv`` will search for that
    version of Python on the ``PATH`` and create a new virtual
    environment based on it.  ``asv`` does not handle downloading and
    installing different versions of Python for you.  They must
    already be installed and on the path.  Depending on your platform,
    you can install multiple versions of Python using your package
    manager or using `pyenv <https://github.com/yyuu/pyenv>`_.

- an executable name on the ``PATH`` or an absolute path to an
  executable.  In this case, the environment is assumed to be already
  fully loaded and read-only.  Thus, the benchmarked project must
  already be installed, and it will not be possible to benchmark
  multiple revisions of the project.

``matrix``
----------
Defines a matrix of third-party dependencies to run the benchmarks with.

If provided, it must be a dictionary, where the keys are the names of
dependencies and the values are lists of versions (as strings) of that
dependency.  An empty string means the "latest" version of that
dependency available on PyPI. Value of ``null`` means the package will
not be installed.

If the list is empty, it is equivalent to ``[""]``, in other words,
the "latest" version.

For example, the following will test with two different versions of
Numpy, the latest version of Cython, and six installed as the latest
version and not installed at all::

    "matrix": {
        "numpy": ["1.7", "1.8"],
        "Cython": []
        "six": ["", null]
    }

The matrix dependencies are installed *before* any dependencies that
the project being benchmarked may specify in its ``setup.py`` file.

.. note::

    At present, this functionality only supports dependencies that are
    installable via ``pip`` or ``conda`` (depending on which
    environment is used). If ``conda`` is specified as ``environment_type``
    and you wish to install the package via ``pip``, then preface the package
    name with ``pip+``. For example, ``emcee`` is only available from ``pip``,
    so the package name to be used is ``pip+emcee``.

``exclude``
-----------
Combinations of libraries, Python versions, or platforms to be
excluded from the combination matrix. If provided, must be a list of
dictionaries, each specifying an exclude rule.

An exclude rule consists of key-value pairs, specifying matching rules
``matrix[key] ~ value``. The values are strings containing regular
expressions that should match whole strings.  The exclude rule matches
if all of the items in it match.

In addition to entries in ``matrix``, the following special keys are
available:

- ``python``: Python version (from ``pythons``)

- ``sys_platform``: Current platform, as in ``sys.platform``.
  Common values are: ``linux2``, ``win32``, ``cygwin``, ``darwin``.

- ``environment_type``: The environment type in use (from ``environment_type``).

For example::

    "pythons": ["2.6", "2.7"],
    "matrix": {
        "numpy": ["1.7", "1.8"],
        "Cython": ["", null],
        "colorama": ["", null],
    },
    "exclude": [
        {"python": "2.6", "numpy": "1.7"},
        {"sys_platform": "(?!win32).*", "colorama": ""},
        {"sys_platform": "win32", "colorama": null},
    ]

This will generate all combinations of Python version and items in the
matrix, except those with Python 2.6 and Numpy 1.7. In other words,
the combinations::

    python==2.6 numpy==1.8 Cython==latest (colorama==latest)
    python==2.6 numpy==1.8 (colorama==latest)
    python==2.7 numpy==1.7 Cython==latest (colorama==latest)
    python==2.7 numpy==1.7 (colorama==latest)
    python==2.7 numpy==1.8 Cython==latest (colorama==latest)
    python==2.7 numpy==1.8 (colorama==latest)

The ``colorama`` package will be installed only if the current
platform is Windows.

``include``
-----------
Additional package combinations to be included as environments.

If specified, must be a list of dictionaries, indicating
the versions of packages to be installed. The dictionary must also
include a ``python`` key specifying the Python version.

In addition, the following keys can be present: ``sys_platform``,
``environment_type``.  If present, the include rule is active only if
the values match, using same matching rules as explained for
``exclude`` above.

The exclude rules are not applied to includes.

For example::

    "include": [
        {'python': '2.7', 'numpy': '1.8.2'},
        {'platform': 'win32', 'environment_type': 'conda', 'python': '2.7',
         'libpython': ''}
    ]

This corresponds to two additional environments. One runs on Python 2.7
and including the specified version of Numpy. The second is active only
for Conda on Windows, and installs the latest version of ``libpython``.

``benchmark_dir``
-----------------
The directory, relative to the current directory, that benchmarks are
stored in.  Should rarely need to be overridden.  If not provided,
defaults to ``"benchmarks"``.

``environment_type``
--------------------
Specifies the tool to use to create environments.  May be "conda",
"virtualenv" or another value depending on the plugins in use.  If
missing or the empty string, the tool will be automatically determined
by looking for tools on the ``PATH`` environment variable.

``env_dir``
-----------
The directory, relative to the current directory, to cache the Python
environments in.  If not provided, defaults to ``"env"``.

``results_dir``
---------------
The directory, relative to the current directory, that the raw results
are stored in.  If not provided, defaults to ``"results"``.

``html_dir``
------------
The directory, relative to the current directory, to save the website
content in.  If not provided, defaults to ``"html"``.

``hash_length``
---------------
The number of characters to retain in the commit hashes when displayed
in the web interface.  The default value of 8 should be more than
enough for most projects, but projects with extremely large history
may need to increase this value.  This does not affect the storage of
results, where the full commit hash is always retained.

``plugins``
-----------
A list of modules to import containing asv plugins.

``wheel_cache_size``
--------------------
The number of wheels (builds) to cache for each environment.

``regressions_first_commits``
-----------------------------

The commits after which the regression search in `asv publish`
should start looking for regressions.

The value is a dictionary mapping benchmark identifier regexps to
commits after which to look for regressions. The benchmark identifiers
are of the form ``benchmark_name(parameters)@branch``, where
``(parameters)`` is present only for parameterized benchmarks. If the
commit identifier is `null`, regression detection for the matching
benchmark is skipped.  The default is to start from the first commit
with results.

Example::

    "regressions_first_commits": {
        ".*": "v0.1.0",
        "benchmark_1": "80fca08d",
        "benchmark_2@master": null,
    }

In this case, regressions are detected only for commits after tag
``v0.1.0`` for all benchmarks. For ``benchmark_1``, regression
detection is further limited to commits after the commit given, and
for ``benchmark_2``, regression detection is skipped completely in the
``master`` branch.

``regressions_thresholds``
--------------------------

The minimum relative change required before `asv publish` reports a
regression.

The value is a dictionary, similar to ``regressions_first_commits``.
If multiple entries match, the largest threshold is taken.  If no
entry matches, the default threshold is ``0.05`` (iow. 5%).

Example::

    "regressions_thresholds": {
        ".*": 0.01,
        "benchmark_1": 0.2,
    }

In this case, the reporting threshold is 1% for all benchmarks, except
``benchmark_1`` which uses a threshold of 20%.
