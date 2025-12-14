# SPDX-License-Identifier: BSD-3-Clause


def peakmem_list():
    # One element takes sizeof(void*) bytes; the code below uses up
    # 4MB (32-bit) or 8MB (64-bit)
    obj = [0] * 2**20
    for _ in obj:
        pass
