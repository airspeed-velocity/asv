# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import io
import os
import platform
import json
import sys

from . import util


class Machine(object):
    def __init__(self):
        path = self.get_machine_file_path()
        if not os.path.exists(path):
            self.generate_machine_file(path)
        self.load_machine_file(path)

    @staticmethod
    def get_machine_file_path():
        return os.path.expanduser('~/.asv-machine')

    def generate_machine_file(self, path):
        from numpy.distutils import cpuinfo
        import psutil

        if not sys.stdout.isatty():
            raise RuntimeError(
                "No ASV machine info file found at '{0}'.\n"
                "Run asv at the console the first time to generate "
                "one.".format(path))

        print("No ASV machine info file found.")
        print("I will now ask you some questions about this machine to "
              "identify it in the benchmarks.")
        print()

        (system, node, release, version, machine, processor) = platform.uname()

        print(
            "1. NAME: A unique name to identify this machine in the results.")
        name = util.get_answer_default("NAME", node)

        print("2. OS: The OS type and version of this machine.")
        operating_system = util.get_answer_default(
            "OS", "{0} {1}".format(system, release))

        print("3. ARCH: The architecture of the machine, e.g. i386")
        arch = util.get_answer_default("ARCH", platform.machine())

        print("4. CPU: A human-readable description of the CPU.")
        if sys.platform.startswith('linux'):
            info = cpuinfo.cpuinfo().info
            cpu = "{0} ({1} cores)".format(info[0]['model name'], len(info))
        else:
            # TODO: Get this on a Mac
            cpu = ''
        cpu = util.get_answer_default("CPU", cpu)

        print("4. RAM: The amount of physical RAM in the system.")
        ram = util.human_file_size(psutil.phymem_usage().total)
        ram = util.get_answer_default("RAM", ram)

        util.write_json(path, {
            "machine": name,
            "os": operating_system,
            "arch": arch,
            "cpu": cpu,
            "ram": ram
        })

    def load_machine_file(self, path):
        d = util.load_json(path)
        self.__dict__.update(d)

    def copy_machine_file(self, results_dir):
        path = os.path.join(results_dir, self.name, 'machine.json')
        util.write_json(path, self.__dict__)
