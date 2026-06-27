# Licensed under a 3-clause BSD style license - see LICENSE.rst

import importlib
import pkgutil
import re
import sys

from . import commands, plugins
from .console import log

# First-party environment backends shipped in asv.plugins.
# Conda / rattler / uv / pixi / micromamba are not in-tree; optional third-party
# plugins register Environment subclasses via conf ``plugins``, entry points
# group ``asv.plugins``, or conventional ``asv_env_<type>`` modules — all
# coordinated by :mod:`asv.envmgmt.discover` when an ``environment_type`` is
# resolved (not only at import time).
ENV_PLUGIN_REGEXES = [
    r"\.virtualenv$",
]


class PluginManager:
    """
    A class to load and manage plugins.

    By default in asv, plugins are searched for in the :py:mod:`asv.plugins`
    namespace package and in the :py:mod:`asv.commands` package.

    Then, any modules specified in the ``plugins`` entry in the
    ``asv.conf.json`` file are loaded — preferably through
    :func:`asv.envmgmt.discover.ensure_conf_backends` so library and CLI share
    one path; ``Command.run_from_args`` delegates there.
    """

    def __init__(self):
        self._plugins = []
        self._imported_names = set()

    def load_plugins(self, package):
        prefix = package.__name__ + "."
        for module_finder, name, ispkg in pkgutil.iter_modules(package.__path__, prefix):
            try:
                mod = importlib.import_module(name)
                self.init_plugin(mod)
                self._plugins.append(mod)
                self._imported_names.add(name)
            except ModuleNotFoundError as err:
                if any(re.search(regex, name) for regex in ENV_PLUGIN_REGEXES):
                    continue  # Fine to not have these
                else:
                    log.error(f"Couldn't load {name} because\n{err}")

    def _load_plugin_by_name(self, name):
        prefix = plugins.__name__ + "."
        for module_finder, module_name, ispkg in pkgutil.iter_modules(plugins.__path__, prefix):
            if name in module_name:
                mod = importlib.import_module(module_name)
                return mod
        return None

    def import_plugin(self, name):
        """Load a plugin by module name.

        - ``.local_mod`` — import ``local_mod`` from the current working directory
        - ``asv_env_*`` / other absolute names — ``importlib.import_module``
        - short names still resolved under ``asv.plugins`` for compatibility

        Idempotent for the same absolute module name.
        """
        if name in self._imported_names and not name.startswith("."):
            return
        extended = False
        if name.startswith("."):
            extended = True
            sys.path.insert(0, ".")
            name = name[1:]
        try:
            mod = None
            if extended:
                mod = importlib.import_module(name)
            else:
                try:
                    mod = importlib.import_module(name)
                except ModuleNotFoundError:
                    mod = self._load_plugin_by_name(name)
            if mod is None:
                raise ModuleNotFoundError(
                    f"ASV plugin module {name!r} could not be imported "
                    f"(install the package or fix the name in conf plugins)"
                )
            self.init_plugin(mod)
            self._plugins.append(mod)
            self._imported_names.add(getattr(mod, "__name__", name))
            if not name.startswith("."):
                self._imported_names.add(name)
        finally:
            if extended:
                del sys.path[0]

    def init_plugin(self, mod):
        if hasattr(mod, "setup"):
            mod.setup()

    def run_hook(self, hook_name, args, kwargs):
        for plugin in self._plugins:
            if hasattr(plugin, hook_name):
                getattr(plugin, hook_name)(*args, **kwargs)


# Import-time: in-tree commands + asv.plugins only (virtualenv, dvcs, …).
# Optional env backends are **not** loaded here with swallowed errors; they are
# discovered on demand via asv.envmgmt.discover when environment_type is set.
plugin_manager = PluginManager()
plugin_manager.load_plugins(commands)
plugin_manager.load_plugins(plugins)
