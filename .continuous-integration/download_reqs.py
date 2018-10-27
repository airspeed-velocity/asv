#!/usr/bin/env python
"""
download_reqs.py [OPTIONS]

Pre-download required packages to cache for conda.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import sys
import os
import shutil
import argparse
import subprocess
import shlex
import time
import textwrap
import tempfile


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

        # Ensure conda-build dependencies are downloaded
        tmpd = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmpd, 'meta.yaml'), 'w') as f:
                f.write(textwrap.dedent("""\
                package:
                  name: "foo"
                  version: "1.0.0"
                source:
                  path: {path}
                build:
                  number: 0
                  script: "python -c pass"
                requirements:
                  host:
                    - pip
                    - python {{{{ python }}}}
                  run:
                    - python
                about:
                  license: BSD
                  summary: Dummy test package
                """.format(path=tmpd)))

            call("""
            conda build --output-folder=xxx --no-anaconda-upload --python={ver[0]}.{ver[1]} .
            """, subs, cwd=tmpd)
        finally:
            shutil.rmtree(tmpd)


def call(cmds, subs=None, **kwargs):
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
        subprocess.check_call(parts, **kwargs)


if __name__ == "__main__":
    main()
