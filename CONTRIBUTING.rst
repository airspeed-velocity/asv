Contributing
============

We love pull requests from everyone. By participating in this project,
you agree to abide by the contributor covenant suggested `code of
conduct <https://github.com/airspeed-velocity/asv/blob/main/CODE_OF_CONDUCT.md>`__.

We Use `Github Flow <https://docs.github.com/en/get-started/using-github/github-flow>`__, So All Code Changes Happen Through Pull Requests
------------------------------------------------------------------------------------------------------------------------------------------

Pull requests are the best way to propose changes to the codebase (we
use `Github
Flow <https://guides.github.com/introduction/flow/index.html>`__). We
actively welcome your pull requests:

1. Fork the repo and create your branch from ``main``.
2. If you’ve added code that should be tested, add tests.
3. If you’ve changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!
7. (optional) Add a release note if necessary.

Commit Style
------------

A sample **good commit** is:

.. code:: diff

   fileName: Thing I did
   Some subHeading things

   So this change was to do that thing I thought was good. Also there was this
   other person who thought so too, so then I ate a sandwich and we got the code
   done. I am writing this but really, honestly, two people did this.


   Co-authored-by: Joel Doe <joel@iexistreally.com>

A good commit should have:

-  The name of the file, or the topic or the subject you have changed or
   the namespace or the functionality you have added **something:**
-  A line describing **something:**
-  An *(optional)* subheading with more details
-  An *(optional)* paragraph or essay on why the change was done and
   anything else you want to share with the devs.
-  **Co-authorship** IS MANDATORY if applicable.

.. raw:: html

   <!-- * Follow our [style guide][style]. -->

.. raw:: html

   <!-- [style]: https://github.com/thoughtbot/guides/tree/master/style -->

Automated Styles
================

A ``pre-commit`` job is setup on CI to enforce consistent styles, so it
is best to set it up locally as well (using
`pipx <https://pypa.github.io/pipx>`__ for isolation):

.. code:: sh

   # Run before committing
   pipx run pre-commit run --all-files
   # Or install the git hook to enforce this
   pipx run pre-commit install

Changelog management
====================

We use reST for the changelog fragments, and they are stored under
``changelog.d``

-  Use pull requests to number the snippets
-  Build a final variant with:
   ``towncrier build --version 0.6.3 --date "$(date -u +%Y-%m-%d)"``
-  Supported categories are:
-  ``feat``
-  ``api``
-  ``bugfix``
-  ``misc``

Here are some sample use cases:

.. code:: sh

   towncrier create -c "Fancy new feature but with a PR attached" +new_thing.added.rst
   towncrier create -c "Require C++17 only" 1.misc.rst

The generated files can be modified later as well.


..
   References
   [1] d-SEAMS: https://github.com/d-SEAMS/seams-core
   [2] Flowy: https://github.com/flowy-code/flowy/blob/main/CONTRIBUTING.md
   [3] Transcriptase: https://gist.github.com/briandk/3d2e8b3ec8daf5a27a62
   [4] readcon: https://github.com/HaoZeke/readCon
