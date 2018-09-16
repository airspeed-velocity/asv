#!/usr/bin/env python
"""
download_reqs.py [OPTIONS]

Pre-download required packages to cache for conda.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
import argparse
import subprocess
import shlex
import time


PY_VERSIONS = [sys.version_info]
if sys.version_info < (3,):
    PY_VERSIONS.append((3, 6))
else:
    PY_VERSIONS.append((2, 7))


def main():
    p = argparse.ArgumentParser(usage=__doc__.strip())
    args = p.parse_args()

    start_time = time.time()

    do_conda()

    end_time = time.time()
    print("Downloading took {} sec".format(end_time - start_time))


def do_conda():
    subs = dict(index_cache='', ver=sys.version_info)

    call("""
    conda create --download-only -n tmp --channel conda-forge -q --yes python={ver[0]}.{ver[1]} conda-build bzip2
    """, subs)

    for pyver in PY_VERSIONS:
        subs['ver'] = pyver
        call("""
        conda create --download-only -n tmp -q --yes --use-index-cache python={ver[0]}.{ver[1]} wheel pip conda-build bzip2
        """, subs)


def call(cmds, subs=None):
    if subs is None:
        subs = {}
    cmds = cmds.splitlines()
    for line in cmds:
        line = line.strip()
        if not line:
            continue
        parts = [x.format(**subs) for x in shlex.split(line)]
        parts = [x for x in parts if x]
        print("$ {}".format(" ".join(parts)))
        sys.stdout.flush()
        subprocess.check_call(parts)


if __name__ == "__main__":
    main()
