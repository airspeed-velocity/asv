# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import argparse

from .. import __version__


def add_global_arguments(parser, suppress_defaults=True):
    # Suppressing defaults is needed in order to allow global
    # arguments both before and after subcommand. Only the top-level
    # parser should have suppress_defaults=False

    if suppress_defaults:
        suppressor = dict(default=argparse.SUPPRESS)
    else:
        suppressor = dict()

    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Increase verbosity",
        **suppressor)

    parser.add_argument(
        "--config",
        help="Benchmark configuration file",
        default=(argparse.SUPPRESS if suppress_defaults else 'asv.conf.json'))

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
        help="Print program version",
        **suppressor)


def add_compare(parser, only_changed_default=False, sort_default='name'):
    parser.add_argument(
        '--factor', "-f", type=float, default=1.1,
        help="""The factor above or below which a result is considered
        problematic.  For example, with a factor of 1.1 (the default
        value), if a benchmark gets 10%% slower or faster, it will
        be displayed in the results list.""")

    parser.add_argument(
        '--split', '-s', action='store_true',
        help="""Split the output into a table of benchmarks that have
        improved, stayed the same, and gotten worse.""")

    parser.add_argument(
        '--only-changed', action='store_true', default=only_changed_default,
        help="""Whether to show only changed results.""")

    parser.add_argument('--no-only-changed', dest='only_changed', action='store_false')

    parser.add_argument(
        '--sort', action='store', type=str, choices=('name', 'ratio'),
        default=sort_default, help="""Sort order""")


def add_show_stderr(parser):
    parser.add_argument(
        "--show-stderr", "-e", action="store_true",
        help="""Display the stderr output from the benchmarks.""")


class DictionaryArgAction(argparse.Action):
    """
    Parses multiple key=value assignments into a dictionary.
    """
    def __init__(self, option_strings, dest, converters=None, choices=None, **kwargs):
        if converters is None:
            converters = {}
        self.converters = converters
        self.__choices = choices
        super(DictionaryArgAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # Parse and check value
        try:
            key, value = values.split("=", 1)
        except ValueError:
            raise argparse.ArgumentError(self,
                                         "{!r} is not a key=value assignment".format(values))

        if self.__choices is not None and key not in self.__choices:
            raise argparse.ArgumentError(self,
                                         "{!r} cannot be set".format(key))

        conv = self.converters.get(key, None)
        if conv is not None:
            try:
                value = conv(value)
            except ValueError as exc:
                raise argparse.ArgumentError(self,
                                             "{!r}: {}".format(key, exc))

        # Store value
        result = getattr(namespace, self.dest, None)
        if result is None:
            result = {}
        result[key] = value
        setattr(namespace, self.dest, result)


def add_bench(parser):
    parser.add_argument(
        "--bench", "-b", type=str, action="append",
        help="""Regular expression(s) for benchmark to run.  When not
        provided, all benchmarks are run.""")

    converters = {
        'timeout': float,
        'version': str,
        'warmup_time': float,
        'repeat': int,
        'number': int,
        'processes': int,
        'sample_time': float
    }

    parser.add_argument(
        "--attribute", "-a", action=DictionaryArgAction,
        choices=tuple(converters.keys()), converters=converters,
        help="""Override a benchmark attribute, e.g. `-a repeat=10`.""")


def add_machine(parser):
    parser.add_argument(
        "--machine", "-m", type=str, default=None,
        help="""Use the given name to retrieve machine information.
        If not provided, the hostname is used.  If no entry with that
        name is found, and there is only one entry in
        ~/.asv-machine.json, that one entry will be used.""")


class PythonArgAction(argparse.Action):
    """
    Backward compatibility --python XYZ argument,
    will be interpreted as --environment :XYZ
    """
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed")
        super(PythonArgAction, self).__init__(option_strings, dest, nargs=1, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, "env_spec", []))
        if values == "same":
            items.extend(["existing:same"])
        else:
            items.extend([":" + value for value in values])
        setattr(namespace, "env_spec", items)


def add_environment(parser, default_same=False):
    help = """Specify the environment and Python versions for running the
        benchmarks. String of the format 'environment_type:python_version',
        for example 'conda:2.7'. If the Python version is not specified,
        all those listed in the configuration file are run. The special
        environment type 'existing:/path/to/python' runs the benchmarks
        using the given Python interpreter; if the path is omitted,
        the Python running asv is used. For 'existing', the benchmarked
        project must be already installed, including all dependencies.
        """

    if default_same:
        help += "The default value is 'existing:same'"
    else:
        help += """By default, uses the values specified in the
            configuration file."""

    parser.add_argument(
        "-E", "--environment",
        dest="env_spec",
        action="append",
        default=[],
        help=help)

    # The --python argument exists for backward compatibility.  It
    # will just set the part after ':' in the environment spec.
    parser.add_argument(
        "--python", action=PythonArgAction, metavar="PYTHON",
        help="Same as --environment=:PYTHON")


def add_parallel(parser):
    parser.add_argument(
        "--parallel", "-j", nargs='?', type=int, default=1, const=-1,
        help="""Build (but don't benchmark) in parallel.  The value is
        the number of CPUs to use, or if no number provided, use the
        number of cores on this machine.""")


def positive_int(string):
    try:
        value = int(string)
        if not value > 0:
            raise argparse.ArgumentTypeError("%r is not a positive integer" % (string,))
        return value
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not an integer" % (string,))
