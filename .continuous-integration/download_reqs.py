#!/usr/bin/env python
"""
download_reqs.py [OPTIONS]

Pre-download required packages to cache for pip and/or conda.
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
    p.add_argument('--pip', action='store', default=None,
                   help="download files for offline pip cache")
    p.add_argument('--conda', action='store_true',
                   help=("download files to conda cache.\n"
                         "NOTE: modifies current conda environment!"))
    args = p.parse_args()

    start_time = time.time()

    if args.pip:
        do_pip(args.pip)
    if args.conda:
        do_conda()

    end_time = time.time()
    print("Downloading took {} sec".format(end_time - start_time))


def do_conda():
    subs = dict(index_cache='', ver=sys.version_info)

    call("""
    conda create --download-only -n tmp --channel conda-forge -q --yes python={ver[0]}.{ver[1]}
    """, subs)

    for pyver in PY_VERSIONS:
        subs['ver'] = pyver
        call("""
        conda create --download-only -n tmp -q --yes --use-index-cache python={ver[0]}.{ver[1]} wheel pip six=1.10 colorama=0.3.7
        conda create --download-only -n tmp -q --yes --use-index-cache python={ver[0]}.{ver[1]} wheel pip six colorama=0.3.9
        """, subs)


def do_pip(cache_dir):
    subs = dict(cache_dir=cache_dir)
    for pyver in PY_VERSIONS:
        if pyver == sys.version_info:
            python = sys.executable
        else:
            python = 'python{ver[0]}.{ver[1]}'.format(ver=pyver)
        if has_python(python):
            subs['python'] = python
            call("""
            {python} -mpip download -d {cache_dir} six==1.10 colorama==0.3.7
            {python} -mpip download -d {cache_dir} six colorama==0.3.9
            """, subs)


def has_python(cmd):
    try:
        ret = subprocess.call([cmd, '--version'])
        return (ret == 0)
    except OSError:
        return False


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
