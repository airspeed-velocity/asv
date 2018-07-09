0.2.2 (unreleased)
------------------

New Features
^^^^^^^^^^^^

API Changes
^^^^^^^^^^^

Bug Fixes
^^^^^^^^^

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^


0.2.2rc1 (2018-07-09)
---------------------

Bugfix release with minor feature additions.

New Features
^^^^^^^^^^^^

- Add a ``--no-pull`` option to ``asv publish`` and ``asv run`` (#592)
- Add a ``--rewrite`` option to ``asv gh-pages`` and fix bugs (#578, #529)
- Add a ``--html-dir`` option to ``asv publish`` (#545)
- Add a ``--yes`` option to ``asv machine`` (#540)
- Enable running via ``python -masv`` (#538)

Bug Fixes
^^^^^^^^^

- Fix support for mercurial >= 4.5 (#643)
- Fix detection of git subrepositories (#642)
- Find conda executable in the "official" way (#646)
- Hide tracebacks in testing functions (#601)
- Launch virtualenv in a more sensible way (#555)
- Disable user site directory also when using conda (#553)
- Set PIP_USER to false when running an executable (#524)
- Set PATH for commands launched inside environments (#541)
- os.environ can only contain bytes on Win/py2 (#528)
- Fix hglib encoding issues on Python 3 (#508)
- Set GIT_CEILING_DIRECTORIES for Git (#636)
- Run pip via python -mpip to avoid shebang limits (#569)
- Always use https URLs (#583)
- Add a min-height on graphs to avoid a flot traceback (#596)
- Escape label html text in plot legends (#614)
- Fixup CI, test, etc issues (#616, #552, #601, #586, #554, #549, #571, #527, #560, #565)


0.2.1 (2017-06-22)
------------------

Bug Fixes
^^^^^^^^^

- Use process groups on Windows (#489)
- Sanitize html filenames (#498)
- Fix incorrect date formatting + default sort order in web ui (#504)


0.2 (2016-10-22)
----------------

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

0.2rc2 (2016-10-17)
-------------------

Same as 0.2.

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
