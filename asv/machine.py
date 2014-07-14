# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import platform
import sys
import textwrap

from . import console
from . import util


def iter_machine_files(results_dir):
    """
    Iterate over all of the machine.json files in the results_dir
    """
    for root, dirs, files in os.walk(results_dir):
        for filename in files:
            if filename == 'machine.json':
                path = os.path.join(root, filename)
                yield path


class MachineCollection(object):
    """
    Stores information about 1 or more machines in the
    ~/.asv-machine.json file.
    """
    api_version = 1

    @staticmethod
    def get_machine_file_path():
        return os.path.expanduser('~/.asv-machine.json')

    @classmethod
    def load(cls, machine_name, _path=None):
        if _path is None:
            path = cls.get_machine_file_path()
        else:
            path = _path

        if os.path.exists(path):
            d = util.load_json(path, cls.api_version)
            if machine_name in d:
                return d[machine_name]

        raise ValueError(
            "No information stored about machine {0}".format(machine_name))

    @classmethod
    def save(cls, machine_name, machine_info, _path=None):
        if _path is None:
            path = cls.get_machine_file_path()
        else:
            path = _path
        if os.path.exists(path):
            d = util.load_json(path)
        else:
            d = {}
        d[machine_name] = machine_info
        util.write_json(path, d, cls.api_version)

    @classmethod
    def update(cls):
        path = cls.get_machine_file_path()
        if os.path.exists(path):
            util.update_json(cls, path, cls.api_version)


class Machine(object):
    """
    Stores information about a particular machine.
    """
    api_version = 1

    fields = [
        ("machine",
         """
         A unique name to identify this machine in the results.  May
         be anything, as long as it is unique across all the machines used
         to benchmark this project."""),

        ("os",
         """
         The OS type and version of this machine.  For example,
         'Macintosh OS-X 10.8'."""),

        ("arch",
         """
         The generic CPU architecture of this machine.  For
         example, 'i386' or 'x86_64'."""),

        ("cpu",
         """
         A specific description of the CPU of this machine,
         including its speed and class.  For example, 'Intel(R)
         Core(TM) i5-2520M CPU @ 2.50GHz (4 cores)'."""),

        ("ram",
         """
         The amount of physical RAM on this machine.  For example,
         '4GB'.""")
    ]

    hardcoded_machine_name = None

    @classmethod
    def get_unique_machine_name(cls):
        if cls.hardcoded_machine_name:
            return cls.hardcoded_machine_name
        (system, node, release, version, machine, processor) = platform.uname()
        return node

    @staticmethod
    def get_defaults():
        (system, node, release, version, machine, processor) = platform.uname()

        cpu = util.get_cpu_info()

        ram = util.get_memsize()

        return {
            'machine': node,
            'os': "{0} {1}".format(system, release),
            'arch': platform.machine(),
            'cpu': cpu,
            'ram': ram
            }

    @staticmethod
    def generate_machine_file():
        if not sys.stdout.isatty():
            raise RuntimeError(
                "Run asv at the console the first time to generate "
                "one.".format(path))

        print("I will now ask you some questions about this machine to "
              "identify it in the benchmarks.")
        print()

        defaults = Machine.get_defaults()
        values = {}

        for i, (name, description) in enumerate(Machine.fields):
            print(
                textwrap.fill(
                    '{0}. {1}: {2}'.format(
                        i+1, name, textwrap.dedent(description)),
                    subsequent_indent='   '))
            values[name] = console.get_answer_default(name, defaults[name])

        return values

    @classmethod
    def load(cls, interactive=False, force_interactive=False, _path=None,
             use_defaults=False, **kwargs):
        self = Machine()
        if use_defaults:
            self.__dict__.update(cls.get_defaults())
            return self

        unique_machine_name = cls.get_unique_machine_name()
        try:
            d = MachineCollection.load(unique_machine_name, _path=_path)
        except ValueError:
            d = {}
        d.update(kwargs)
        if (not len(d) and interactive) or force_interactive:
            d.update(self.generate_machine_file())

        self.__dict__.update(d)
        MachineCollection.save(unique_machine_name, self.__dict__, _path=_path)
        return self

    def save(self, results_dir):
        path = os.path.join(results_dir, self.machine, 'machine.json')
        util.write_json(path, self.__dict__, self.api_version)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
