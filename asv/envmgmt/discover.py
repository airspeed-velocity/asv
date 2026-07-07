# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Host-side environment backend discovery (target architecture).

Resolution of an ``environment_type`` string goes through
:func:`ensure_environment_backend` / :func:`resolve_environment_class`.
Both CLI and library callers use this API; ``Command`` is not required.

Entry points
------------
Group **``asv.environment_backends``** (not the historic catch-all
``asv.plugins`` name for module lists).

    [project.entry-points."asv.environment_backends"]
    conda = "asv_env_conda:Conda"   # class or zero-arg factory preferred
    # transitional: module path still accepted if it registers tool_name

EP **name** = ``environment_type`` / ``tool_name``.
EP **value** = class, zero-arg factory returning a class, or (legacy) module.

Built-ins
---------
``virtualenv`` and ``existing`` ship in core (loaded via ``asv.plugins``
bootstrap). Optional backends (conda, rattler, uv, mamba, pixi, …) are
**out-of-tree** packages that register via entry points — not in-tree
``asv.plugins`` modules.

Precedence (deterministic)
--------------------------
1. Already-registered subclass with matching ``tool_name`` (core: virtualenv/existing).
2. Conf ``plugins`` module imports (explicit user request; fail closed).
3. Entry points in ``asv.environment_backends`` for this type (duplicate
   providers → fail closed; load error / tool_name mismatch → fail closed).
4. Optional legacy conventional module ``asv_env_<type>`` only if
   ``ASV_ENV_LEGACY_MODULE_FALLBACK`` is set to a truthy value (transitional;
   emits a warning). Fail closed if present but broken.
5. ``EnvironmentUnavailable`` with registered names and a *generic* install
   hint (``pip install "asv[<type>]"`` or provide an entry point) — no
   personal GitHub org URLs in core.

Empty ``environment_type`` defaults to ``virtualenv`` (predictable CI;
does not auto-select by ``matches()`` among installed packages).

Host only (asv >= 3.9). Do not import this from asv_runner / in-env code.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import warnings
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from asv.console import log

ENTRY_POINT_GROUP = "asv.environment_backends"
# Historic group accepted only when explicitly enabled (migration aid).
LEGACY_ENTRY_POINT_GROUP = "asv.plugins"
CONVENTIONAL_MODULE_PREFIX = "asv_env_"
# Reserved core names — optional backends must not steal these via EPs.
CORE_RESERVED_TOOL_NAMES = frozenset({"virtualenv", "existing"})

_success_cache: dict = {}


def conventional_module_name(environment_type: str) -> str:
    return f"{CONVENTIONAL_MODULE_PREFIX}{environment_type}"


def legacy_module_fallback_enabled() -> bool:
    """Transitional ``asv_env_<type>`` import; off by default."""
    val = os.environ.get("ASV_ENV_LEGACY_MODULE_FALLBACK", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def _environment_base():
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


def _load_conf_plugins(plugins: Sequence[str]) -> List[str]:
    from asv.plugin_manager import plugin_manager
    from asv.environment import EnvironmentUnavailable

    loaded = []
    for name in plugins:
        try:
            plugin_manager.import_plugin(name)
        except Exception as err:
            raise EnvironmentUnavailable(
                f"Failed loading conf plugin {name!r}: {err}. "
                f"Registered tool_names: {registered_tool_names()}."
            ) from err
        loaded.append(name)
    return loaded


def _iter_entry_points(group: str):
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


def _entry_points_for_type(environment_type: str) -> list:
    """All EPs whose name equals environment_type (primary group, then legacy)."""
    found = [ep for ep in _iter_entry_points(ENTRY_POINT_GROUP) if ep.name == environment_type]
    if found:
        return found
    # Do not auto-use legacy group for optional types that core also ships
    # unless no primary-group EP exists at all for this process — still scan
    # legacy only when primary empty for this type.
    legacy = [
        ep for ep in _iter_entry_points(LEGACY_ENTRY_POINT_GROUP) if ep.name == environment_type
    ]
    return legacy


def _coerce_ep_to_class(obj, environment_type: str):
    """Turn EP load result into an Environment subclass (or None to re-scan)."""
    from asv.environment import Environment

    if obj is None:
        return None
    # Zero-arg factory
    if not isinstance(obj, type) and callable(obj):
        try:
            obj = obj()
        except TypeError:
            pass
    if isinstance(obj, type) and issubclass(obj, Environment):
        if getattr(obj, "tool_name", None) != environment_type:
            raise ValueError(
                f"backend class {obj!r} has tool_name="
                f"{getattr(obj, 'tool_name', None)!r}, expected {environment_type!r}"
            )
        return obj
    # Module: side-effect registration; caller re-finds by tool_name
    if hasattr(obj, "__dict__") and getattr(obj, "__name__", None):
        # module object — prefer class with matching tool_name on module
        for attr in vars(obj).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Environment)
                and getattr(attr, "tool_name", None) == environment_type
            ):
                return attr
        return None
    raise TypeError(
        f"entry point for {environment_type!r} loaded {obj!r}; "
        f"expected Environment subclass, zero-arg factory, or module"
    )


def _load_entry_point_class(environment_type: str):
    """Return Environment subclass from EPs or raise EnvironmentUnavailable."""
    from asv.environment import EnvironmentUnavailable

    eps = _entry_points_for_type(environment_type)
    if not eps:
        return None

    if len(eps) > 1:
        providers = []
        for ep in eps:
            dist = getattr(ep, "dist", None)
            providers.append(
                f"{ep.value}" + (f" (from {dist})" if dist is not None else "")
            )
        raise EnvironmentUnavailable(
            f"Multiple entry points provide environment_type={environment_type!r} "
            f"in group {ENTRY_POINT_GROUP!r} (or legacy {LEGACY_ENTRY_POINT_GROUP!r}): "
            f"{providers}. Remove or rename duplicates."
        )

    ep = eps[0]
    try:
        raw = ep.load()
    except Exception as err:
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r}: entry point {ep.name!r} "
            f"(value {ep.value!r}) failed to load: {err}. "
            f"Registered tool_names: {registered_tool_names()}."
        ) from err

    try:
        cls = _coerce_ep_to_class(raw, environment_type)
    except (TypeError, ValueError) as err:
        raise EnvironmentUnavailable(
            f"environment_type={environment_type!r}: entry point {ep.name!r} "
            f"(value {ep.value!r}) invalid: {err}. "
            f"Registered tool_names: {registered_tool_names()}."
        ) from err

    if cls is not None:
        return cls

    # Module loaded without an obvious class — subclass may still have registered
    cls = find_registered_class(environment_type)
    if cls is not None:
        return cls

    raise EnvironmentUnavailable(
        f"environment_type={environment_type!r}: entry point {ep.name!r} "
        f"(value {ep.value!r}) loaded but no Environment subclass with "
        f"tool_name={environment_type!r} is available. "
        f"Registered tool_names: {registered_tool_names()}."
    )


def _load_conventional_module(environment_type: str) -> Tuple[bool, Optional[str], Any]:
    """Legacy fallback. Returns (attempted, error_or_None, class_or_None)."""
    mod_name = conventional_module_name(environment_type)
    try:
        if importlib.util.find_spec(mod_name) is None:
            return False, None, None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False, None, None
    try:
        mod = importlib.import_module(mod_name)
    except Exception as err:
        return True, (
            f"installed module {mod_name!r} failed to import for "
            f"environment_type={environment_type!r}: {err}"
        ), None
    try:
        cls = _coerce_ep_to_class(mod, environment_type)
    except (TypeError, ValueError) as err:
        return True, str(err), None
    if cls is not None:
        return True, None, cls
    cls = find_registered_class(environment_type)
    if cls is not None:
        return True, None, cls
    return True, (
        f"imported {mod_name!r} but no Environment subclass with "
        f"tool_name={environment_type!r}"
    ), None


def ensure_environment_backend(
    environment_type: str,
    conf=None,
    plugins: Optional[Iterable[str]] = None,
    *,
    use_cache: bool = True,
):
    """Resolve an Environment subclass for *environment_type* or fail closed."""
    from asv.environment import EnvironmentUnavailable

    if not environment_type:
        environment_type = "virtualenv"

    if plugins is None:
        plugin_list = list(_plugins_from_conf(conf))
    else:
        plugin_list = list(plugins)

    cache_key = (environment_type, tuple(plugin_list), legacy_module_fallback_enabled())
    if use_cache and cache_key in _success_cache:
        return _success_cache[cache_key]

    tried: List[str] = []

    # 1) already registered (in-tree bootstrap or prior import)
    cls = find_registered_class(environment_type)
    if cls is not None:
        if use_cache:
            _success_cache[cache_key] = cls
        return cls

    # Optional backends must not claim core reserved names via EP-only path
    # when not already registered (should not happen for virtualenv/existing).

    # 2) conf plugins
    if plugin_list:
        tried.append(f"conf plugins={plugin_list!r}")
        _load_conf_plugins(plugin_list)
        cls = find_registered_class(environment_type)
        if cls is not None:
            if use_cache:
                _success_cache[cache_key] = cls
            return cls

    # 3) entry points
    tried.append(f"entry point group={ENTRY_POINT_GROUP!r} name={environment_type!r}")
    cls = _load_entry_point_class(environment_type)
    if cls is not None:
        if use_cache:
            _success_cache[cache_key] = cls
        return cls

    # 4) legacy conventional module (opt-in)
    if legacy_module_fallback_enabled():
        mod_name = conventional_module_name(environment_type)
        tried.append(f"legacy module {mod_name!r} (ASV_ENV_LEGACY_MODULE_FALLBACK)")
        attempted, err, cls = _load_conventional_module(environment_type)
        if attempted and err is not None:
            raise EnvironmentUnavailable(
                f"environment_type={environment_type!r} legacy module present but "
                f"failed (fail closed): {err}. "
                f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
            )
        if attempted and cls is not None:
            warnings.warn(
                f"Resolved environment_type={environment_type!r} via transitional "
                f"module {mod_name!r}; prefer an entry point in group "
                f"{ENTRY_POINT_GROUP!r} or an asv optional extra.",
                UserWarning,
                stacklevel=2,
            )
            if use_cache:
                _success_cache[cache_key] = cls
            return cls

    # 5) missing
    raise EnvironmentUnavailable(
        f"Unknown environment type {environment_type!r}. "
        f"Install a package that provides entry point "
        f"{environment_type!r} in group {ENTRY_POINT_GROUP!r} "
        f"(for example pip install \"asv[{environment_type}]\" when that extra "
        f"exists), or list a local module in conf plugins. "
        f"Registered tool_names: {registered_tool_names()}. Tried: {tried}."
    )


def resolve_environment_class(
    environment_type: str,
    conf=None,
    plugins: Optional[Iterable[str]] = None,
):
    """Public alias for :func:`ensure_environment_backend`."""
    return ensure_environment_backend(environment_type, conf=conf, plugins=plugins)


def ensure_conf_backends(conf) -> Any:
    """Import conf ``plugins`` and ensure ``conf.environment_type`` resolves."""
    env_type = getattr(conf, "environment_type", None) or "virtualenv"
    plugins = list(getattr(conf, "plugins", None) or [])
    if plugins:
        _load_conf_plugins(plugins)
    return ensure_environment_backend(env_type, conf=conf, plugins=plugins)


def clear_discovery_cache() -> None:
    """Test helper: drop successful resolution memo."""
    _success_cache.clear()


__all__ = [
    "ENTRY_POINT_GROUP",
    "LEGACY_ENTRY_POINT_GROUP",
    "CONVENTIONAL_MODULE_PREFIX",
    "CORE_RESERVED_TOOL_NAMES",
    "conventional_module_name",
    "legacy_module_fallback_enabled",
    "registered_tool_names",
    "find_registered_class",
    "ensure_environment_backend",
    "resolve_environment_class",
    "ensure_conf_backends",
    "clear_discovery_cache",
]
