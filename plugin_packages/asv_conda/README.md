# asv_conda

**Shell/CLI-oriented** ASV backend (`environment_type = "conda"`). Uses the `conda` executable (`CONDA_EXE` / `PATH`). This is the backend expected to stay process-based.

For **libmamba APIs** use **asv_mamba**. For **py-rattler APIs** use **asv_rattler** / **asv_pixi**.

```json
{ "environment_type": "conda", "plugins": ["asv_conda"] }
```
