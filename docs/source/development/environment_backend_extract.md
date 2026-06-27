# Environment backend extraction (design spike)

**Status:** design + structural preview on branch `design/env-backend-extract`.  
**Not merged.** Conf schema (`environment_type`, `matrix` with `req` / `env` / `env_nobuild`, include/exclude) stays stable.

## Problem today

`asv/environment.py` (~1100 lines) mixes:

1. **Matrix expansion** — Cartesian product over Python versions and `matrix` axes, include/exclude rules (`iter_matrix`, `_parse_matrix`, `match_rule`).
2. **Env identity / caching** — directory names and hashes from tool + python + requirements + tagged env vars (`get_env_name`).
3. **Lifecycle orchestration** — create, install project wheel, run benchmarks, build cache (`Environment` methods).
4. **Implicit backend assumptions** — subclasses in `asv/plugins/{conda,virtualenv,uv,rattler}.py` override chunks of that lifecycle; adding a backend means subclassing a fat base and knowing install-command substitution rules.

Tracker pressure (non-exhaustive):

| Issue | Theme |
|-------|--------|
| [#1542](https://github.com/airspeed-velocity/asv/issues/1542) | `matrix` constraints vs multi-step `install_command` (conda then pip ignores joint solve) |
| [#1543](https://github.com/airspeed-velocity/asv/issues/1543) | Joint PyPI + conda solve |
| [#1436](https://github.com/airspeed-velocity/asv/issues/1436) | Resolvers / env management RFC (uv, rattler, SBOM) |
| [#1534](https://github.com/airspeed-velocity/asv/issues/1534) / rattler follow-ups | Backend-specific solve failures |
| [#1537](https://github.com/airspeed-velocity/asv/issues/1537) | `--python=same` / host env leakage |
| [#1561](https://github.com/airspeed-velocity/asv/issues/1561), [#1433](https://github.com/airspeed-velocity/asv/issues/1433) | uv as first-class env type / install story |

This spike does **not** implement single-solve matrix semantics (#1542). It defines seams so that work becomes possible without growing `environment.py`.

## Proposed seams

```
asv.conf.json
    │
    ▼
┌───────────────────┐
│  Matrix iteration │  pure config → list of env specs
│  (matrix_pure +   │  no imports of asv.plugins.*
│   iter_matrix)    │
└─────────┬─────────┘
          │ EnvSpec (python, reqs, env vars, tool name)
          ▼
┌───────────────────┐
│  Env facade       │  owns paths, build cache keys, install_command templates
│  (Environment /   │  delegates tool ops to a backend
│   EnvironmentFacade)│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  EnvironmentBackend│  create / install_project / run / python_executable
│  (protocol)        │  one implementation per tool
└───────────────────┘
     │         │        │
 virtualenv   conda    uv / rattler / existing
```

### 1. Matrix iteration (pure)

- Input: `environment_type`, python list, `conf.matrix`, exclude/include rules.
- Output: combinations keyed by `('req'|'env'|'env_nobuild'|'python', name)`.
- **Must not** import concrete plugin modules. Default tool selection may call an injected `get_environment_class(conf, python)` callback (today that still lives in `asv.environment` to avoid circular imports).
- Unit-testable without conda/rattler installed.

### 2. Env-spec facade

- Holds: python string, requirement map, tagged env vars, conf-derived paths (`env_dir`), project install commands.
- Computes **order-insensitive** fingerprints for caching (`asv.envmgmt.identity`).
- Calls backend for tool-specific create/install/run.
- Long-term: `asv.environment.Environment` becomes this facade (or a thin subclass for backward compatibility).

### 3. Tool backend protocol

See `asv.envmgmt.protocol.EnvironmentBackend`:

- `create()`, `install_project(...)`, `run(...)`, `python_executable()`
- Optional `identity_payload(...)` for tool-specific hash salt

Plugins today remain subclasses of `Environment` for compatibility. Preview adapter: `asv.envmgmt.virtualenv_backend.VirtualenvBackend` (records operations; can resolve interpreter via existing `Virtualenv._find_python`).

### 4. Install / build commands

Stay on the facade. Backends should not parse `asv.conf.json`. Substitution of `{wheel_file}`, `{build_dir}`, etc. remains orchestration. Follow-up for #1542: a **SolverBackend** optional capability (joint solve) vs **InstallerBackend** (multi-step).

## Stability guarantees

| Surface | Guarantee in this design |
|---------|---------------------------|
| `asv.conf.json` keys | Unchanged (`environment_type`, `matrix`, include/exclude, install/build commands) |
| `get_environments` / `get_environment_class` | Keep resolving the same tool name strings |
| Plugin entry points | Existing in-tree plugins keep working; third-party `Environment` subclasses get a documented deprecation window when methods move to backends |
| Result env hashes | Prefer identical hashes for permutation-equivalent requirement dicts (new helpers); full migration must not reshuffle on-disk env dirs without a migration note |

## Migration phases

1. **This PR (spike):** `asv.envmgmt` package + design doc + focused tests; legacy `Environment` untouched on production paths.
2. **Delegate:** `Environment` methods call backend instance when present; virtualenv fully on protocol.
3. **Port conda / uv / rattler / existing** one PR each.
4. **Optional solver API** for joint matrix+project solve (#1542/#1543) behind capability flags.
5. **Remove** fat overrides once all in-tree backends are thin.

## Non-goals (this PR)

- Merging to `main`.
- Implementing joint conda+pip solve or locking formats (SBOM / uv lock).
- New backends (pixi, micromamba) beyond documentation.
- Changing `asv_runner` (benchmark process side).

## Layout (preview)

```
asv/envmgmt/
  protocol.py           # EnvironmentBackend ABC
  identity.py           # requirements_fingerprint, env_spec_fingerprint
  matrix_pure.py        # parse_matrix, match_rule, cartesian_combinations
  facade.py             # EnvironmentFacade
  virtualenv_backend.py # adapter preview
docs/source/development/environment_backend_extract.md  # this file
test/test_envmgmt_extract.py
```

## How to review

1. Read this doc and issue #1542 / #1436 for motivation.
2. Read `protocol.py` + `facade.py` for the intended boundary.
3. Run `pytest test/test_envmgmt_extract.py` (no conda required).
4. Confirm `asv.environment.get_environment_class` still works for `virtualenv` / `existing`.
