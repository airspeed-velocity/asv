# Licensed under a 3-clause BSD style license - see LICENSE.rst

from .run import Run

from . import common_args


class Dev(Run):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "dev", help="Do a test run of a benchmark suite during development",
            description="""
                This runs a benchmark suite in a mode that is useful
                during development.  It is equivalent to
                ``asv run --python=same``""")

        cls._setup_arguments(parser, env_default_same=True)

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run(cls, conf, **kwargs):
        if not kwargs.get("env_spec"):
            kwargs["env_spec"] = ["existing:same"]
        return super(cls, Dev).run(conf=conf, **kwargs)
