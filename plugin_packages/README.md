# External ASV environment plugins

Core ASV on this branch only ships **virtualenv**. These packages restore the former in-tree backends:

| Package | `environment_type` | Needs |
|---------|-------------------|--------|
| `asv_conda` | `conda` | `conda` CLI |
| `asv_mamba` | `mamba` | `mamba` or conda + `asv_conda` |
| `asv_rattler` | `rattler` | `py-rattler` |
| `asv_uv` | `uv` | `uv` CLI |

```bash
pip install -e ./plugin_packages/asv_conda
# asv.conf.json
# "environment_type": "conda",
# "plugins": ["asv_conda"]
```

Load order: list plugin modules in `plugins` before running ASV commands.
