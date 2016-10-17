0.2rc2 (2016-10-17)
-------------------

New Features
^^^^^^^^^^^^

- Automatic detection and listing of performance regressions. (#236)
- Support for Windows. (#282)
- New ``setup_cache`` method. (#277)
- Exclude/include rules in configuration matrix. (#329)
- Command-line option for selecting environments. (#352)
- Possibility to include packages via pip in conda environments. (#373)
- The ``pretty_name`` attribute can be used to change the display
  name of benchmarks. (#425)
- Git submodules are supported. (#426)
- The time when benchmarks were run is tracked. (#428)
- New summary web page showing a list of benchmarks. (#437)
- Atom feed for regressions. (#447)
- PyPy support. (#452)

API Changes
^^^^^^^^^^^

- The parent directory of the benchmark suite is no longer inserted
  into ``sys.path``. (#307)
- Repository mirrors are no longer created for local repositories. (#314)
- In asv.conf.json matrix, ``null`` previously meant (undocumented)
  the latest version. Now it means that the package is to not be
  installed. (#329)
- Previously, the ``setup`` and ``teardown`` methods were run only once
  even when the benchmark method was run multiple times, for example due
  to ``repeat > 1`` being present in timing benchmarks. This is now
  changed so that also they are run multiple times. (#316)
- The default branch for Mercurial is now ``default``, not ``tip``. (#394)
- Benchmark results are now by default ordered by commit, not by date. (#429)
- When ``asv run`` and other commands are called without specifying
  revisions, the default values are taken from the branches in
  ``asv.conf.json``. (#430)
- The default value for ``--factor`` in ``asv continuous`` and
  ``asv compare`` was changed from 2.0 to 1.1 (#469).

Bug Fixes
^^^^^^^^^

- Output will display on non-Unicode consoles. (#313, #318, #336)
- Longer default install timeout. (#342)
- Many other bugfixes and minor improvements.

0.1.1 (2015-05-05)
------------------

First full release.

0.1rc3 (2015-05-01)
-------------------

Bug Fixes
^^^^^^^^^
Include pip_requirements.txt.

Display version correctly in docs.

0.1rc2 (2015-05-01)
-------------------

0.1rc1 (2015-05-01)
-------------------
