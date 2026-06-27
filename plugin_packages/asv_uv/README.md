# asv_uv

`environment_type = "uv"` without requiring the `uv` CLI. Uses **stdlib `venv`** + **`python -m pip`** (in-process / interpreter APIs). When Astral ships a stable Python API for uv’s resolver, prefer that here.

For true multi-version isolation matching `uv venv --python=…`, ensure the requested interpreter is on `PATH` (same constraint as core `virtualenv`).
