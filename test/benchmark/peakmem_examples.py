# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)


def peakmem_list():
    # One element takes sizeof(void*) bytes; the code below uses up
    # 4MB (32-bit) or 8MB (64-bit)
    obj = [0] * 2**20
    for x in obj:
        pass
