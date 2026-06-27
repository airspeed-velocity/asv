# External ASV environment plugins

Core ASV ships **virtualenv** only. Install plugins for other backends.

| Package | `environment_type` | Transport **now** | Notes |
|---------|-------------------|-------------------|--------|
| **asv_conda** | `conda` | **Shell / CLI** | Only long-term CLI plugin |
| **asv_mamba** | `mamba` | **libmambapy API** | Needs libmambapy (conda-forge); no conda CLI |
| **asv_rattler** | `rattler` | **py-rattler API** | `solve` / `install` |
| **asv_pixi** | `pixi` | **py-rattler API** | Pixi stack APIs via rattler (not `pixi` CLI, not PyPI name collision) |
| **asv_uv** | `uv` | **stdlib venv + pip** | No uv CLI required; swap in uv library APIs when stable |

```bash
pip install -e . -e ./plugin_packages/asv_rattler -e ./plugin_packages/asv_pixi
```
