On Python 3.11 and newer, start benchmark subprocesses in their own process
group with ``process_group=0`` instead of a ``preexec_fn``. Running Python code
in the forked child is not safe when other threads are alive, and on PyPy it
could hang ``asv run`` before the benchmark started.
