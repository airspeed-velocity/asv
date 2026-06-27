Performance reporting on pull requests
======================================

Common use case is to run the benchmarks on your pull requests,
to see if the changes you made have any impact on the performance.

In this tutorial we will implement that with:

* ``git`` for the source control
* GitHub for the repository
* GitHub Actions for CI/CD
* ``asv v0.6.4`` as the benchmarking tool
* ``main`` as the base branch

The result will look like this:

.. image:: ./_static/asv-report.png
   :alt: asv report

Overall, this workflow can be broken down into four steps:

1. When a pull request is made, this triggers a Github Action workflow.
2. The first workflow compares performance between commits and saves the report in a file.
3. Second workflow is triggered when the report is saved.
4. This second workflow adds the report to the PR as a comment.

.. note::

   In GitHub, two workflows are needed so this works even with PRs made from forks.

   If a PR is made from a fork, then the first workflow doesn't have sufficient permissions
   to make comments on the PR, because the PR lives in the main repository. This serves as a
   security measure against malicious PRs.

   But since the second workflow is not connected to the PR, it has wider permissions and can
   make comments on the PR.

1. Setup ``asv``
-------------------

Install ``asv`` in your project.

.. code-block:: bash

   pip install asv

And setup ``asv``:

.. code-block:: bash

   asv quickstart


This will create a ``asv.conf.json`` file in your project, as well as a ``benchmarks`` directory with some example benchmarks.

Next head over to ``asv.conf.json`` and configure the dependencies and Python version you want to use.

2. Write your benchmarks
-------------------------

For the purpose of this tutorial, we will go ahead with the benchmarks generated with ``asv quickstart``.

After you have written your benchmarks, check that they work:

.. code-block:: bash

   asv run HEAD^! -v -e


This will generate benchmark results as JSON files. These files will be saved in a directory as specified in the ``results_dir`` field in the ``asv.conf.json`` file.

By default, this is ``.asv/results``.

.. note::

   What does ``HEAD^!`` mean?

   We're using ``asv`` with git, and so the argument to ``asv run`` is a git range.

   * ``HEAD`` means the "current branch".

   * ``^`` means that we mean the COMMIT of the branch, not the BRANCH itself.

     * Without ``^``, we would run benchmarks for the whole branch history.
     * With ``^``, we run benchmarks FROM the latest commit (incl) TO ...

   * ``!`` means that we want to select range spanning a single commit.

     * Without ``!``, we run benchmarks for all commits FROM the latest commit
       TO the start of the branch history.
     * With ``!``, we run benchmarks ONLY FOR the latest commit.

To check that the results are correct, start-up a local web server with:

.. code-block:: bash

   asv publish
   asv preview

This will start a local web server on port 8080.

3. Run only a subset of benchmarks
-----------------------------------

If you have a lot of benchmarks, you might want to run only a subset of them for the PRs.

For example, in `django-components <https://django-components.github.io/django-components/>`_,
we decided to run only a single end-to-end test for the PRs.

The full test suite took 5 minutes, whereas a single test took only about 1 minute.

To easily select which benchmarks run on PR, you can use the ``@benchmark`` decorator
defined below. With it, you can add benchmark metadata
(`benchmark attributes <https://asv.readthedocs.io/en/latest/benchmarks.html>`_) directly
on your benchmark functions:

.. code-block:: python

   @benchmark(
       pretty_name="My Benchmark",
       number=1,
       rounds=5,
   )
   def time_my_benchmark(self):
       ...

And to select which benchmarks run on PR, you can pass ``include_in_quick_benchmark=True`` to the decorator:

.. code-block:: python

   @benchmark(
       pretty_name="My Benchmark",
       number=1,
       rounds=5,
       include_in_quick_benchmark=True,
   )
   def time_my_benchmark(self):
       ...

The implementation of the ``@benchmark`` decorator includes a check for the ``DJC_BENCHMARK_QUICK`` environment variable.

* If ``DJC_BENCHMARK_QUICK`` is set, then only benchmarks with ``include_in_quick_benchmark=True`` are run.
* If ``DJC_BENCHMARK_QUICK`` is NOT set, then ALL benchmarks are run.

This will allow us to set the "quick" mode for PRs from within the workflow.

Here is the full implementation of the ``@benchmark`` decorator:

.. code-block:: python

   import os
   from typing import Any, Dict, List, Optional

   def benchmark(
       *,
       include_in_quick_benchmark: bool = False,
       **kwargs,
   ):
       def decorator(func):
           # For pull requests, we want to benchmark only a subset of tests,
           # because the full set of tests takes too long to run.
           # This is done by passing in `DJC_BENCHMARK_QUICK=1` as an environment variable.
           if os.getenv("DJC_BENCHMARK_QUICK") and not include_in_quick_benchmark:
               # NOTE: `asv` requires `benchmark_name` to:
               # - MUST NOT CONTAIN `-`
               # - MUST START WITH `time_`, `mem_`, `peakmem_`
               # See https://github.com/airspeed-velocity/asv/pull/1470
               #
               # If we set the benchmark name to something that does NOT start with
               # valid prefixes like `time_`, `mem_`, or `peakmem_`, this function will be
               # ignored by asv, and hence not run.
               func.benchmark_name = "noop"
               return func

           # Additional, untyped kwargs
           for k, v in kwargs.items():
               setattr(func, k, v)

           return func

       return decorator


4. Trigger benchmarks on PRs
-----------------------------

Now that the benchmark tests are prepared, we can move on to setting up GitHub Actions.

Let's add the first workflow which will compare the PR with ``main``.

Paste the following in ``.github/workflows/pr-benchmark-comment.yml``:

.. code-block:: yaml

   # Run benchmark report on pull requests to main.
   # The report is added to the PR as a comment.
   #
   # NOTE: When making a PR from a fork, the worker doesn't have sufficient
   # access to make comments on the target repo's PR. And so, this workflow
   # is split to two parts:
   #
   # 1. Benchmarking and saving results as artifacts
   # 2. Downloading the results and commenting on the PR
   #
   # See https://stackoverflow.com/a/71683208/9788634
   
   name: PR benchmarks generate
   
   on:
     pull_request:
       branches: [main]

   jobs:
     benchmark:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
           with:
             fetch-depth: 0
   
         # Fetch main so we can benchmark against it
         - name: Fetch base branch
           run: |
             git remote add upstream https://github.com/${{ github.repository }}.git
             git fetch upstream main
   
         - name: Set up Python
           uses: actions/setup-python@v5
           with:
             python-version: "3.13"
             cache: "pip"
   
         - name: Install dependencies
           run: |
             python -m pip install --upgrade pip
             pip install asv
   
         - name: Run benchmarks
           run: |
             # Prepare the profile under which the benchmarks will be saved.
             # We assume that the CI machine has a name that is unique and stable.
             # See https://github.com/airspeed-velocity/asv/issues/796#issuecomment-1188431794
             echo "Preparing benchmarks profile..."
             asv machine --yes
             echo "Benchmarks profile DONE."
   
             # Generate benchmark data
             # - `^` means that we mean the COMMIT of the branch, not the BRANCH itself.
             #       Without it, we would run benchmarks for the whole branch history.
             #       With it, we run benchmarks FROM the latest commit (incl) TO ...
             # - `!` means that we want to select range spanning a single commit.
             #       Without it, we would run benchmarks for all commits FROM the latest commit
             #       TO the start of the branch history.
             #       With it, we run benchmarks ONLY FOR the latest commit.
             echo "Running benchmarks for upstream/main..."
             DJC_BENCHMARK_QUICK=1 asv run upstream/main^! -v
             echo "Benchmarks for upstream/main DONE."
             echo "Running benchmarks for HEAD..."
             DJC_BENCHMARK_QUICK=1 asv run HEAD^! -v
             echo "Benchmarks for HEAD DONE."
   
             # Compare against main
             echo "Comparing benchmarks..."
             mkdir -p pr
             asv compare upstream/main HEAD --factor 1.1 --split > ./pr/benchmark_results.md
             echo "Benchmarks comparison DONE."
   
         - name: Save benchmark results
           uses: actions/upload-artifact@v4
           with:
             name: benchmark_results
             path: pr/

.. note::

   Similarly to the previously seen ``HEAD^!`` argument, here we use:

   * ``upstream/main^!`` to benchmark the latest commit of ``main``
   * ``HEAD^!`` to benchmark the latest commit of the PR

5. Download the results and post them to the PR
-----------------------------------------------

As mentioned in the beginning, the first workflow doesn't have sufficient permissions to make comments on the PR.

So we need to add a second workflow that will download the results and post them to the PR.

Paste the following in ``.github/workflows/pr-benchmark-comment.yml``:

.. code-block:: yaml

   # Run benchmark report on pull requests to main.
   # The report is added to the PR as a comment.
   #
   # NOTE: When making a PR from a fork, the worker doesn't have sufficient
   # access to make comments on the target repo's PR. And so, this workflow
   # is split to two parts:
   #
   # 1. Benchmarking and saving results as artifacts
   # 2. Downloading the results and commenting on the PR
   #
   # See https://stackoverflow.com/a/71683208/9788634
   
   name: PR benchmark comment
   
   on:
     workflow_run:
       # NOTE: The name here MUST match the name of the workflow that generates the data
       workflows: [PR benchmarks generate]
       types:
         - completed
   
   jobs:
     download:
       runs-on: ubuntu-latest
       permissions:
         contents: write
         pull-requests: write
         repository-projects: write
       steps:
         # NOTE: The next two steps (download and unzip) are equivalent to using `actions/download-artifact@v4`
         #       However, `download-artifact` was not picking up the artifact, while the REST client does.
         - name: Download benchmark results
           uses: actions/github-script@v7
           with:
             script: |
               const fs = require('fs');
   
               // Find the artifact that was generated by the "pr-benchmark-generate" workflow
               const allArtifacts = await github.rest.actions.listWorkflowRunArtifacts({
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 # Explicitly search the workflow run that generated the the results
                 # (AKA the "pr-benchmark-generate" workflow).
                 run_id: context.payload.workflow_run.id,
               });
               const matchArtifact = allArtifacts.data.artifacts.filter((artifact) => {
                 return artifact.name == "benchmark_results"
               })[0];
   
               # Download the artifact
               const download = await github.rest.actions.downloadArtifact({
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 artifact_id: matchArtifact.id,
                 archive_format: 'zip',
               });
               fs.writeFileSync(
                 `${process.env.GITHUB_WORKSPACE}/benchmark_results.zip`,
                 Buffer.from(download.data),
               );
   
         - name: Unzip artifact
           run: unzip benchmark_results.zip
   
         - name: Comment on PR
           # See https://github.com/actions/github-script
           uses: actions/github-script@v7
           with:
             github-token: ${{ secrets.GITHUB_TOKEN }}
             script: |
               const fs = require('fs');
               const results = fs.readFileSync('./benchmark_results.md', 'utf8');
               const body = `## Performance Benchmark Results\n\nComparing PR changes against main branch:\n\n${results}`;
   
               # See https://octokit.github.io/rest.js/v21/#issues-create-comment
               await github.rest.issues.createComment({
                 body: body,
                 # See https://github.com/actions/toolkit/blob/662b9d91f584bf29efbc41b86723e0e376010e41/packages/github/src/context.ts#L66
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 issue_number: context.payload.workflow_run.pull_requests[0].number,
               });

6. Test the integration
-----------------------

To see the integration in action, merge the code above into your repository.

Then make a PR and see the results in the PR comment.

You should also see the "PR benchmarks generate" and "PR benchmarks comment" workflows running
in GitHub's Actions tab.

.. note::

   If you're using ``master`` instead of ``main``, then update the files above accordingly.

7. Troubleshooting
------------------

The comment posting workflow may be flaky. In such case, please check the following,
add these debug logs to the workflow, and then re-run the workflow:

Paste the following in ``.github/workflows/pr-benchmark-comment.yml``:

.. code-block:: yaml

   # Run benchmark report on pull requests to main.
   # The report is added to the PR as a comment.
   #
   # NOTE: When making a PR from a fork, the worker doesn't have sufficient
   # access to make comments on the target repo's PR. And so, this workflow
   # is split to two parts:
   #
   # 1. Benchmarking and saving results as artifacts
   # 2. Downloading the results and commenting on the PR
   #
   # See https://stackoverflow.com/a/71683208/9788634
   
   name: PR benchmark comment
   
   on:
     workflow_run:
       # NOTE: The name here MUST match the name of the workflow that generates the data
       workflows: [PR benchmarks generate]
       types:
         - completed
   
   jobs:
     download:
       runs-on: ubuntu-latest
       permissions:
         contents: write
         pull-requests: write
         repository-projects: write
       steps:
         ########## USE FOR DEBUGGING ##########
         - name: Debug
           uses: actions/github-script@v7
           with:
             script: |
               console.log('Workflow Run ID:', context.payload.workflow_run.id);
               const artifacts = await github.rest.actions.listWorkflowRunArtifacts({
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 run_id: context.payload.workflow_run.id
               });
               console.log('Available artifacts:');
               console.log(JSON.stringify(artifacts.data, null, 2));
               console.log(`PRs: ` + JSON.stringify(context.payload.workflow_run.pull_requests));
         #########################################
   
         # NOTE: The next two steps (download and unzip) are equivalent to using `actions/download-artifact@v4`
         #       However, `download-artifact` was not picking up the artifact, while the REST client does.
         - name: Download benchmark results
           uses: actions/github-script@v7
           with:
             script: |
               const fs = require('fs');
   
               // Find the artifact that was generated by the "pr-benchmark-generate" workflow
               const allArtifacts = await github.rest.actions.listWorkflowRunArtifacts({
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 # Explicitly search the workflow run that generated the the results
                 # (AKA the "pr-benchmark-generate" workflow).
                 run_id: context.payload.workflow_run.id,
               });
               const matchArtifact = allArtifacts.data.artifacts.filter((artifact) => {
                 return artifact.name == "benchmark_results"
               })[0];
   
               # Download the artifact
               const download = await github.rest.actions.downloadArtifact({
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 artifact_id: matchArtifact.id,
                 archive_format: 'zip',
               });
               fs.writeFileSync(
                 `${process.env.GITHUB_WORKSPACE}/benchmark_results.zip`,
                 Buffer.from(download.data),
               );
   
         - name: Unzip artifact
           run: unzip benchmark_results.zip
   
         - name: Comment on PR
           # See https://github.com/actions/github-script
           uses: actions/github-script@v7
           with:
             github-token: ${{ secrets.GITHUB_TOKEN }}
             script: |
               const fs = require('fs');
               const results = fs.readFileSync('./benchmark_results.md', 'utf8');
               const body = `## Performance Benchmark Results\n\nComparing PR changes against main branch:\n\n${results}`;
   
               # See https://octokit.github.io/rest.js/v21/#issues-create-comment
               await github.rest.issues.createComment({
                 body: body,
                 # See https://github.com/actions/toolkit/blob/662b9d91f584bf29efbc41b86723e0e376010e41/packages/github/src/context.ts#L66
                 owner: context.repo.owner,
                 repo: context.repo.repo,
                 issue_number: context.payload.workflow_run.pull_requests[0].number,
               });
