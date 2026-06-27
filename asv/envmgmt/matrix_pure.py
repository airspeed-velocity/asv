# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Matrix parsing helpers with no imports of concrete plugin classes.

``iter_matrix`` in ``asv.environment`` still performs include/exclude and
python iteration because it needs ``get_environment_class`` for default
tool selection. Pure parsing lives here so unit tests do not load conda.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple


Key = Tuple[str, Any]


def parse_matrix(matrix: Mapping[str, Any], bare_keys=()) -> Dict[Key, List[Any]]:
    """Parse conf ``matrix`` into {(key_type, key_name): [values, ...]}."""
    result: Dict[Key, List[Any]] = {}
    if not matrix:
        return result

    for key, value in matrix.items():
        if key in bare_keys:
            key_type = key
            key_name = None
        elif key.startswith("req:"):
            key_type = "req"
            key_name = key[4:]
        elif key.startswith("env:"):
            key_type = "env"
            key_name = key[4:]
        elif key.startswith("env_nobuild:"):
            key_type = "env_nobuild"
            key_name = key[12:]
        else:
            # legacy bare requirement name
            key_type = "req"
            key_name = key

        if not isinstance(value, list):
            value = [value]
        result[(key_type, key_name)] = value
    return result


def parse_rule(rule: Mapping[str, Any], is_include: bool = False) -> Dict[Key, Any]:
    """Normalize an include/exclude rule to the same key space as the matrix."""
    out: Dict[Key, Any] = {}
    for key, value in rule.items():
        if key in ("python", "environment_type", "sys_platform"):
            out[(key, None)] = value
        elif key.startswith("req:"):
            out[("req", key[4:])] = value
        elif key.startswith("env:"):
            out[("env", key[4:])] = value
        elif key.startswith("env_nobuild:"):
            out[("env_nobuild", key[12:])] = value
        else:
            out[("req", key)] = value
    return out


def match_rule(target: Mapping[Key, Any], rule: Mapping[Key, Any]) -> bool:
    """Return True if every field in *rule* matches *target* (ASV semantics)."""
    for key, value in rule.items():
        if key not in target:
            return False
        if target[key] != value:
            # empty string in matrix means "any / unset" in some ASV paths;
            # keep exact equality for the pure helper.
            return False
    return True


def cartesian_combinations(
    python: str, parsed_matrix: Mapping[Key, List[Any]]
) -> Iterable[Dict[Key, Any]]:
    """Yield combinations for one Python version without exclude/include."""
    import itertools

    keys = list(parsed_matrix.keys())
    values = [parsed_matrix[k] if parsed_matrix[k] != [] else [""] for k in keys]
    values = [v if isinstance(v, list) else [v] for v in values]
    all_keys: List[Key] = [("python", None)] + keys
    for combination in itertools.product([python], *values):
        yield dict(zip(all_keys, combination))
