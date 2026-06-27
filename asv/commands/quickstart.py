# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os
import shutil

from asv_runner.console import color_print

from . import Command
from ..console import log

# Pre-existing paths that quickstart can safely reconcile instead of aborting.
# An existing .gitignore is common in real project checkouts (upstream #1582).
_MERGEABLE_TEMPLATE_FILES = frozenset({'.gitignore'})


def _merge_gitignore(template_path, dest_path):
    """Append ASV template .gitignore lines that are missing from dest_path.

    Returns True if any lines were appended.
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        template_lines = f.read().splitlines()
    if os.path.isfile(dest_path):
        with open(dest_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        existing_lines = existing.splitlines()
    else:
        existing = ''
        existing_lines = []

    existing_set = set(existing_lines)
    missing = [line for line in template_lines if line not in existing_set]
    if not missing:
        return False

    parts = []
    if existing and not existing.endswith('\n'):
        parts.append('\n')
    if existing.strip():
        parts.append('\n# --- airspeed velocity (asv quickstart) ---\n')
    parts.append('\n'.join(missing))
    if not parts[-1].endswith('\n'):
        parts.append('\n')
    with open(dest_path, 'a', encoding='utf-8') as f:
        f.write(''.join(parts))
    return True


class Quickstart(Command):
    @classmethod
    def setup_arguments(cls, subparsers):
        parser = subparsers.add_parser(
            "quickstart", help="Create a new benchmarking suite",
            description="Creates a new benchmarking suite")

        parser.add_argument(
            "--dest", "-d", default=".",
            help="The destination directory for the new benchmarking "
            "suite")

        grp = parser.add_mutually_exclusive_group()
        grp.add_argument(
            "--top-level", action="store_true", dest="top_level", default=None,
            help="Use layout suitable for putting the benchmark suite on "
            "the top level of the project's repository")
        grp.add_argument(
            "--no-top-level", action="store_false", dest="top_level", default=None,
            help="Use layout suitable for putting the benchmark suite in "
            "a separate repository")

        parser.set_defaults(func=cls.run_from_args)

        return parser

    @classmethod
    def run_from_args(cls, args):
        return cls.run(dest=args.dest, top_level=args.top_level)

    @classmethod
    def run(cls, dest=".", top_level=None):
        log.info("Setting up new Airspeed Velocity benchmark suite.")

        if top_level is None:
            log.flush()
            color_print("")
            color_print("Which of the following template layouts to use:")
            color_print("(1) benchmark suite at the top level of the project repository")
            color_print("(2) benchmark suite in a separate repository")
            color_print("")
            while True:
                answer = input("Layout to use? [1/2] ")
                if answer.lower()[:1] == "1":
                    top_level = True
                    break
                elif answer.lower()[:1] == "2":
                    top_level = False
                    break
            color_print("")

        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'template')

        conflicts = []
        for entry in sorted(os.listdir(template_path)):
            dest_path = os.path.join(dest, entry)
            if os.path.exists(dest_path) and entry not in _MERGEABLE_TEMPLATE_FILES:
                conflicts.append(entry)

        if conflicts:
            listed = ', '.join(conflicts)
            log.info(f"Template content already exists: {listed}")
            log.info(
                "Remove or rename the conflicting path(s), then re-run quickstart.")
            log.info(
                "Edit asv.conf.json to continue if the suite is already "
                "partially set up.")
            return 1

        for entry in sorted(os.listdir(template_path)):
            path = os.path.join(template_path, entry)
            dest_path = os.path.join(dest, entry)
            if entry in _MERGEABLE_TEMPLATE_FILES and os.path.exists(dest_path):
                if entry == '.gitignore' and os.path.isfile(dest_path):
                    if _merge_gitignore(path, dest_path):
                        log.info("Merged ASV patterns into existing .gitignore")
                    else:
                        log.info(
                            "Existing .gitignore already contains ASV "
                            "template patterns")
                continue
            if os.path.exists(dest_path):
                continue
            if os.path.isdir(path):
                shutil.copytree(path, dest_path)
            elif os.path.isfile(path):
                shutil.copyfile(path, dest_path)

        conf_file = os.path.join(dest, 'asv.conf.json')
        if top_level and os.path.isfile(conf_file):
            with open(conf_file, 'r') as f:
                conf = f.read()

            reps = [('"repo": "",', '"repo": ".",'),
                    ('// "env_dir": "env",', '"env_dir": ".asv/env",'),
                    ('// "results_dir": "results",', '"results_dir": ".asv/results",'),
                    ('// "html_dir": "html",', '"html_dir": ".asv/html",')]
            for src, dst in reps:
                conf = conf.replace(src, dst)

            with open(conf_file, 'w') as f:
                f.write(conf)

        log.info("Edit asv.conf.json to get started.")
