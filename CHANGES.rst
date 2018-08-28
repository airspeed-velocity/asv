0.3b1 (2018-08-29)
------------------

Major release with several new features.

New Features
^^^^^^^^^^^^

- Revised timing benchmarking. ``asv`` will display and record the
  median and interquartile ranges of timing measurement results. The
  information is also used by ``asv compare`` and ``asv continuous``
  in determining what changes are significant. The ``asv run`` command
  has new options for collecting samples. Timing benchmarks have
  new benchmarking parameters for controlling how timing works,
  including  ``processes`` attribute for collect data by running
  benchmarks in different sequential processes.
  The defaults are adjusted to obtain faster benchmarking.
  (#707, #698, #695, #689, #683, #665, #652, #575, #503, #493)

- Interleaved benchmark running. Timing benchmarks can be run in
  interleaved order via ``asv run --interleave-processes``, to obtain
  better sampling over long-time background performance variations.
  (#697, #694, #647)

- Customization of build/install/uninstall commands. (#699)

- Launching benchmarks via a fork server (on Unix-based systems).
  Reduces the import time overheads in launching new
  benchmarks. Default on Linux. (#709, #666)

- Benchmark versioning. Invalidate old benchmark results when
  benchmarks change, via a benchmark ``version``
  attribute. User-configurable, by default based on source
  code. (#509)

- Setting benchmark attributes on command line, via ``--attribute``.
  (#647)

- ``asv show`` command for displaying results on command line. (#711)

- Support for Conda channels. (#539)

- Provide ASV-specific environment variables to launched commands. (#624)

- Show branch/tag names in addition to commit hashes. (#705)

- Support for projects in repository subdirectories. (#611)

- Way to run specific parametrized benchmarks. (#593)

- Group benchmarks in the web benchmark grid (#557)

- Make the web interface URL addresses more copypasteable.
  (#608, #605, #580)

- Allow customizing benchmark display names (#484)

- Don't reinstall project if it is already installed (#708)

API Changes
^^^^^^^^^^^

- The ``goal_time`` attribute in timing benchmarks is removed (and now
  ignored). See documentation on how to tune timing benchmarks now.

- ``asv publish`` may ask you to run ``asv update`` once after upgrading,
  to regenerate ``benchmarks.json`` if ``asv run`` was not yet run.

- If you are using ``asv`` plugins, check their compatibility.  The
  internal APIs in ``asv`` are not guaranteed to be backward
  compatible.

Bug Fixes
^^^^^^^^^

- Fixes in 0.2.1 and 0.2.2 are also included in 0.3.
- Make ``asv compare`` accept named commits (#704)
- Fix ``asv profile --python=same`` (#702)
- Make ``asv compare`` behave correctly with multiple machines/envs (#687)
- Avoid making too long result file names (#675)
- Fix saving profile data (#680)
- Ignore missing branches during benchmark discovery (#674)
- Perform benchmark discovery only when necessary (#568)
- Fix benchmark skipping to operate on a per-environment basis (#603)
- Allow putting ``asv.conf.json`` to benchmark suite directory (#717)
- Miscellaneous minor fixes (#719, #718, #716, #715, #714, #713, #706,
  #701, #691, #688, #684, #682, #660, #634, #615, #600, #573, #556)


Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- www: display regressions separately, one per commit (#720)
- Internal changes. (#712, #700, #681, #663, #662, #637, #613, #606, #572)
- CI/etc changes. (#585, #570)
- Added internal debugging command ``asv.benchmarks`` (#685)
- Make tests not require network connection, except with Conda (#696)
- Drop support for end-of-lifed Python versions 2.6 & 3.2 & 3.3 (#548)


0.2.2 (2018-07-14)
------------------

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
- Disable pip build isolation in wheel_cache (#670)
- Fixup CI, test, etc issues (#616, #552, #601, #586, #554, #549, #571, #527, #560, #565)

0.2.2rc1 (2018-07-09)
---------------------

Same as 0.2.2, minus #670.

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
