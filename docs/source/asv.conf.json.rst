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

Currently, only ``git`` repositories are supported, so this must be a
URL that ``git`` knows how to clone from, for example:

   - git@github.com:spacetelescope/asv.git

   - https://github.com/spacetelescope/asv.git

The repository may be readonly.

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
dependency.  If the list is empty, use the "latest" version of that
dependency available on PyPI.

For example, the following will test with two different versions of
Numpy, and the latest version of Cython::

    "matrix": {
        "numpy": ["1.7", "1.8"],
        "Cython": []
    }

The matrix dependencies are installed *before* any dependencies that
the project being benchmarked may specify in its ``setup.py`` file.

.. note::

    At present, this functionality is rather limited, as it only
    supports dependencies that are installable from PyPI using
    ``pip``, and there is no functionality for limiting the matrix to
    specific combinations.

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
