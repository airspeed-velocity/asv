# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""\
Usage: python -masv.benchmark COMMAND [...]

Manage a single benchmark and, when run from the commandline, report
its runtime to a file.

commands:

  timing [...]
      Run timing benchmark for given Python statement.

internal commands:

  discover BENCHMARK_DIR RESULT_FILE
      Discover benchmarks in a given directory and store result to a file.
  setup_cache BENCHMARK_DIR BENCHMARK_ID
      Run setup_cache for given benchmark.
  run BENCHMARK_DIR BENCHMARK_ID QUICK PROFILE_PATH RESULT_FILE
      Run a given benchmark, and store result in a file.
  run_server BENCHMARK_DIR SOCKET_FILENAME
      Run a Unix socket forkserver.
"""

import sys

from asvcore.discovery import _discover
from asvcore.run import _run
from asvcore.server import _run_server
from asvcore.timing import _timing
from asvcore.setup_cache import _setup_cache
from asvcore.check import _check


def _help(args):
    print(__doc__)


commands = {
    'discover': _discover,
    'setup_cache': _setup_cache,
    'run': _run,
    'run_server': _run_server,
    'check': _check,
    'timing': _timing,
    '-h': _help,
    '--help': _help,
}


def main():
    if len(sys.argv) < 2:
        _help([])
        sys.exit(1)

    mode = sys.argv[1]
    args = sys.argv[2:]

    if mode in commands:
        commands[mode](args)
        sys.exit(0)
    else:
        sys.stderr.write(f"Unknown mode {mode}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
