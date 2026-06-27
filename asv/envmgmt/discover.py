# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Single environment-backend discovery path for ASV.

Resolution of an ``environment_type`` string (``virtualenv``, ``conda``,
``rattler``, …) goes through :func:`ensure_environment_backend` /
:func:`resolve_environment_class`. Both CLI and library callers use this API;
``Command.run_from_args`` is **not** required.

Entry points
------------
Setuptools / importlib.metadata group **``asv.plugins``**. Each optional
backend package (HaoZeke ``asv_env_<type>``) declares e.g.::

    [project.entry-points."asv.plugins"]
    rattler = "asv_env_rattler"

The entry point **name** is the ``environment_type`` / ``tool_name``; the
**value** is the importable module that defines an ``Environment`` subclass
with that ``tool_name``.

Discovery order (deterministic)
-------------------------------
1. Already-registered subclass with matching ``tool_name`` (in-tree
   ``virtualenv`` / ``existing`` after normal ASV import).
2. Import every module listed in conf ``plugins`` (idempotent absolute imports).
3. Load the entry point whose **name** equals ``environment_type`` (fail closed
   if that EP exists but import/register fails or wrong ``tool_name``).
4. If still missing: conventional module ``asv_env_<environment_type>`` when
   importable (``find_spec``); fail closed if the module is installed but
   import or registration fails.
5. Raise :class:`~asv.environment.EnvironmentUnavailable` with registered
   ``tool_name`` s and what was tried.

Missing package with no entry point → unavailable (hard fail for that type),
not a silent fallback to another backend. Fail-closed applies to
"installed/packaged but broken"; "user never installed the extra" is the same
exception class with an install hint.
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any, Iterable, List, Optional, Sequence, Tuple

ENTRY_POINT_GROUP = "asv.plugins"
CONVENTIONAL_MODULE_PREFIX = "asv_env_"

# Memo: (environment_type, frozenset(plugins)) -> class or raised (we only cache success)
_success_cache: dict = {}


def conventional_module_name(environment_type: str) -> str:
    return f"{CONVENTIONAL_MODULE_PREFIX}{environment_type}"


def _environment_base():
    # Late import avoids circular import at package load (environment imports discover).
    from asv.environment import Environment

    return Environment


def _iter_env_subclasses():
    from asv import util

    return util.iter_subclasses(_environment_base())


def registered_tool_names() -> List[str]:
    return [cls.tool_name for cls in _iter_env_subclasses() if cls.tool_name]


def find_registered_class(environment_type: str):
    for cls in _iter_env_subclasses():
        if cls.tool_name == environment_type:
            return cls
    return None


def _plugins_from_conf(conf) -> Tuple[str, ...]:
    if conf is None:
        return ()
    plugins = getattr(conf, "plugins", None) or ()
    return tuple(plugins)


def _import_module_absolute(module_name: str):
    """Import a module by absolute name; returns the module."""
    return importlib.import_module(module_name)


def _load_conf_plugins(plugins: Sequence[str]) -> List[str]:
    """Import conf plugin modules. Returns list of names successfully imported.

    Fail closed: any listed plugin that cannot be imported raises.
    """
    from asv.plugin_manager import plugin_manager

    loaded = []
    for name in plugins:
        # Prefer PluginManager so ``.local`` and legacy short names still work.
        plugin_manager.import_plugin(name)
        loaded.append(name)
    return loaded


def _iter_entry_points(group: str = ENTRY_POINT_GROUP):
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return []
    eps = entry_points()
    try:
        selected = eps.select(group=group)
    except AttributeError:
        selected = eps.get(group, [])
    return list(selected)


def _load_entry_point_for_type(environment_type: str) -> Tuple[bool, Optional[str]]:
    """Load EP named ``environment_type`` if present.

    Returns (found_ep, error_message_or_None).
    If found_ep and error_message is set, caller must fail closed.
    If found_ep and error is None, module was imported (registration checked by caller).
    If not found_ep, no EP with that name (try conventional module next).
    """
    for ep in _iter_entry_points():
        if ep.name != environment_type:
            continue
        try:
            ep.load()
        except Exception as err:
            return True, (
                f"entry point {ep.name!r} in group {ENTRY_POINT_GROUP!r} "
                f"(value {ep.value!r}) failed to load: {err}"
            )
        return True, None
    return False, None


def _module_is_importable(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _load_conventional_module(environment_type: str) -> Tuple[bool, Optional[str]]:
    """Try ``asv_env_<type>``. Returns (attempted, error_or_None).

    attempted=False means dist not installed (no fail-closed for broken package).
    attempted=True with error means fail closed.
    attempted=True with error=None means import succeeded.
    """
    mod_name = conventional_module_name(environment_type)
    if not _module_is_importable(mod_name):
        return False, None
    try:
        _import_module_absolute(mod_name)
    except Exception as err:
        return True, (
            f"installed module {mod_name!r} failed to import for "
            f"environment_type={environment_type!r}: {err}"
        )
    return True, None


def ensure_environment_backend(
    environment_type: str,
    conf=None,
    plugins: Optional[Iterable[str]] = None,
    *,
    use_cache: bool = True,
):
    """Import installed backends until ``tool_name == environment_type`` or fail.

    Parameters
    ----------
    environment_type :
        Conf / matrix type string (e.g. ``\"virtualenv\"``, ``\"rattler\"``).
    conf :
        Optional ASV config object; ``conf.plugins`` used if *plugins* is None.
    plugins :
        Explicit plugin module names (overrides ``conf.plugins`` when not None).
    use_cache :
        Memoize successful resolutions keyed by type + plugin list.

    Returns
    -------
    type
        ``Environment`` subclass with matching ``tool_name``.

    Raises
    ------
    asv.environment.EnvironmentUnavailable
        Type unknown after discovery, or a packaged backend failed to load.
    """
    from asv.environment import EnvironmentUnavailable

    if not environment_type:
        environment_type = "virtualenv"

    if plugins is None:
        plugin_list = list(_plugins_from_conf(conf))
    else:
        plugin_list = list(plugins)

    cache_key = (environment_type, tuple(plugin_list))
    if use_cache and cache_key in _success_cache:
        return _success_cache[cache_key]

    tried: List[str] = []

    cls = find_registered_class(environment_type)
    if cls is not None:
        if use_cache:
            _success_cache[cache_key] = cls
        return cls

    # 2) conf plugins
    if plugin_list:
        tried.append(f"conf plugins={plugin_list!r}")
        try:
            _load_conf_plugins(plugin_list)
        except Exception as err:
            raise EnvironmentUnavailable(
                f"Failed loading conf plugins for environment_type="
                f"{environment_type!r}: {err}. "
                f"Registered tool_names so far: {registered_tool_names()}."
            ) from err
        cls = find_registered_class(environment_type)
        if cls is not None:
            if use_cache:
                _success_cache[cache_key] = cls
            return cls

    # 3) entry point named exactly environment_type
    tried.append(f"entry point group={ENTRY_POINT_GROUP!r} name={environment_type!r}")
    found_ep, ep_err = _load_entry_point_for_type(environment_type)
    if found_ep and ep_err is not None:
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r} entry point present but "
            f"failed (fail closed): {ep_err}. "
            f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
        )
    if found_ep:
        cls = find_registered_class(environment_type)
        if cls is not None:
            if use_cache:
                _success_cache[cache_key] = cls
            return cls
        # EP loaded but did not register expected tool_name — fail closed
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r}: entry point "
            f"{environment_type!r} in group {ENTRY_POINT_GROUP!r} loaded but "
            f"no Environment subclass registered with tool_name="
            f"{environment_type!r}. "
            f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
        )

    # 4) conventional asv_env_<type>
    mod_name = conventional_module_name(environment_type)
    tried.append(f"conventional module {mod_name!r}")
    attempted, conv_err = _load_conventional_module(environment_type)
    if attempted and conv_err is not None:
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r} package appears installed "
            f"but failed (fail closed): {conv_err}. "
            f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
        )
    if attempted:
        cls = find_registered_class(environment_type)
        if cls is not None:
            if use_cache:
                _success_cache[cache_key] = cls
            return cls
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r}: imported {mod_name!r} but "
            f"no Environment subclass registered with tool_name="
            f"{environment_type!r}. "
            f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
        )

    # 5) missing entirely
    raise EnvironmentUnavailable(
        f"Unknown environment type {environment_type!r}. "
        f"Install an optional backend (e.g. pip install asv_env_{environment_type} "
        f"or git+https://github.com/HaoZeke/asv_env_{environment_type}.git), "
        f"declare entry point {environment_type!r} in group {ENTRY_POINT_GROUP!r}, "
        f"and/or list the module in conf plugins. "
        f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
    )


def resolve_environment_class(
    environment_type: str,
    conf=None,
    plugins: Optional[Iterable[str]] = None,
):
    """Public alias: resolve class for *environment_type* via unified discovery."""
    return ensure_environment_backend(environment_type, conf=conf, plugins=plugins)


def ensure_conf_backends(conf) -> Any:
    """Apply conf ``plugins`` and ensure ``conf.environment_type`` is registered.

    Safe to call from library code and from ``Command.run_from_args``.
    Returns the resolved class for ``conf.environment_type`` (default virtualenv).
    """
    env_type = getattr(conf, "environment_type", None) or "virtualenv"
    plugins = list(getattr(conf, "plugins", None) or [])
    # Always import conf plugins even if type already registered (side effects /
    # multiple backends). Then ensure the configured type.
    if plugins:
        try:
            _load_conf_plugins(plugins)
        except Exception as err:
            from asv.environment import EnvironmentUnavailable

            raise EnvironmentUnavailable(
                f"Failed loading conf plugins {plugins!r}: {err}. "
                f"Registered tool_names: {registered_tool_names()}."
            ) from err
    return ensure_environment_backend(env_type, conf=conf, plugins=plugins)


def clear_discovery_cache() -> None:
    """Test helper: drop successful resolution memo."""
    _success_cache.clear()


__all__ = [
    "ENTRY_POINT_GROUP",
    "CONVENTIONAL_MODULE_PREFIX",
    "conventional_module_name",
    "registered_tool_names",
    "find_registered_class",
    "ensure_environment_backend",
    "resolve_environment_class",
    "ensure_conf_backends",
    "clear_discovery_cache",
]
