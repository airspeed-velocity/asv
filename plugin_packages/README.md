# External ASV environment plugins

Core ASV on `design/env-backend-extract` ships **virtualenv** only. Everything else is an installable plugin.

## Orientation

| Package | `environment_type` | Orientation | Status |
|---------|-------------------|-------------|--------|
| *(core)* `virtualenv` | `virtualenv` | local venv + pip | in-tree |
| **asv_conda** | `conda` | **shell / CLI** | ported from former in-tree plugin |
| **asv_mamba** | `mamba` | CLI today; **target: libmamba API** | wraps asv_conda; prefers `mamba` on PATH |
| **asv_rattler** | `rattler` | **API** (py-rattler) | ported; import works without rattler installed |
| **asv_uv** | `uv` | CLI today; **target: uv APIs** | ported |
| **asv_pixi** | `pixi` | **API** (pixi/lib) | **stub** only |

Only **conda** is expected to stay “shell-oriented” long term. Solvers that expose libraries (libmamba, rattler, pixi, future uv APIs) should implement the backend via in-process calls so matrix constraints can participate in a single solve.

```bash
pip install -e . -e ./plugin_packages/asv_conda
```

```json
{
  "environment_type": "conda",
  "plugins": ["asv_conda"]
}
```
