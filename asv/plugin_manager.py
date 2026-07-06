# Licensed under a 3-clause BSD style license - see LICENSE.rst

import importlib
import pkgutil
import re
import sys

from . import commands, plugins
from .console import log

# First-party environment backends under asv.plugins. Missing optional
# tools (if a distro strips them) must not hard-fail bootstrap.
ENV_PLUGIN_REGEXES = [
    r"\.virtualenv$",
    r"\.conda$",
    r"\.rattler$",
    r"\.uv$",
]


class PluginManager:
    """
    Load first-party plugins from ``asv.plugins`` / ``asv.commands``, and
    optional conf module names via :meth:`import_plugin`.

    Environment *type* resolution for optional third-party backends is owned
    by :mod:`asv.envmgmt.discover` (entry point group
    ``asv.environment_backends``), not by this class alone.
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
                    continue
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
        """Load a plugin by module name (conf ``plugins`` / local ``.mod``).

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


plugin_manager = PluginManager()
plugin_manager.load_plugins(commands)
plugin_manager.load_plugins(plugins)
