# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from collections import OrderedDict
import os
import platform
import sys
import textwrap

import six

from . import console
from . import util


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
    def load(cls, machine_name):
        path = cls.get_machine_file_path()
        if os.path.exists(path):
            d = util.load_json(path, cls.api_version)
            if machine_name in d:
                return d[machine_name]

        raise ValueError(
            "No information stored about machine {0}".format(machine_name))

    @classmethod
    def save(cls, machine_name, machine_info):
        path = cls.get_machine_file_path()
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

    fields = OrderedDict([
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
    ])

    @staticmethod
    def get_unique_machine_name():
        (system, node, release, version, machine, processor) = platform.uname()
        return node

    @staticmethod
    def get_defaults():
        (system, node, release, version, machine, processor) = platform.uname()

        if sys.platform.startswith('linux'):
            try:
                from numpy.distutils import cpuinfo
            except ImportError:
                cpu = ''
            else:
                info = cpuinfo.cpuinfo().info
                cpu = "{0} ({1} cores)".format(
                    info[0]['model name'], len(info))
        else:
            # TODO: Get this on a Mac
            cpu = ''

        try:
            import psutil
        except ImportError:
            ram = ''
        else:
            ram = util.human_file_size(psutil.phymem_usage().total)

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

        for i, (name, description) in enumerate(six.iteritems(Machine.fields)):
            print(
                textwrap.fill(
                    '{0}. {1}: {2}'.format(
                        i+1, name, textwrap.dedent(description)),
                    subsequent_indent='   '))
            values[name] = console.get_answer_default(name, defaults[name])

        return values

    @classmethod
    def load(cls, interactive=False, **kwargs):
        self = Machine()

        unique_machine_name = cls.get_unique_machine_name()
        try:
            d = MachineCollection.load(unique_machine_name)
        except ValueError:
            d = {}
        d.update(kwargs)
        if not len(d) and interactive:
            d.update(self.generate_machine_file())

        self.__dict__.update(d)
        MachineCollection.save(unique_machine_name, self.__dict__)
        return self

    def save(self, results_dir):
        path = os.path.join(results_dir, self.machine, 'machine.json')
        util.write_json(path, self.__dict__, self.api_version)

    @classmethod
    def update(cls, path):
        util.update_json(cls, path, cls.api_version)
