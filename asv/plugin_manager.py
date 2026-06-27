# Licensed under a 3-clause BSD style license - see LICENSE.rst

import importlib
import pkgutil
import re
import sys

from . import commands, plugins
from .console import log

# First-party environment backends shipped in asv.plugins.
# Conda / rattler / uv / pixi / micromamba are not in-tree; optional third-party
# plugins may still register Environment subclasses via conf ``plugins``.
ENV_PLUGIN_REGEXES = [
    r"\.virtualenv$",
]


class PluginManager:
    """
    A class to load and manage plugins.

    By default in asv, plugins are searched for in the :py:mod:`asv.plugins`
    namespace package and in the :py:mod:`asv.commands` package.

    Then, any modules specified in the ``plugins`` entry in the
    ``asv.conf.json`` file are loaded.
    """

    def __init__(self):
        self._plugins = []

    def load_plugins(self, package):
        prefix = package.__name__ + "."
        for module_finder, name, ispkg in pkgutil.iter_modules(package.__path__, prefix):
            try:
                mod = importlib.import_module(name)
                self.init_plugin(mod)
                self._plugins.append(mod)
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
        - ``asv_conda`` / other absolute names — ``importlib.import_module``
        - short names still resolved under ``asv.plugins`` for compatibility
        """
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


def load_asv_env_entry_points(pm=None):
    """Load setuptools entry points group ``asv.plugins`` (asv_env_* packages)."""
    pm = pm or plugin_manager
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return
    eps = entry_points()
    # Python 3.10+ vs 3.9
    try:
        selected = eps.select(group="asv.plugins")
    except AttributeError:
        selected = eps.get("asv.plugins", [])
    for ep in selected:
        try:
            ep.load()  # importing registers Environment subclasses
            pm._plugins.append(ep)
        except Exception as err:
            log.error(f"Failed loading entry point {ep.name}: {err}")


plugin_manager = PluginManager()
plugin_manager.load_plugins(commands)
plugin_manager.load_plugins(plugins)
load_asv_env_entry_points(plugin_manager)
