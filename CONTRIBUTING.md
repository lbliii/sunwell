# Contributing

## Dependency installs (PyPI vs local b-stack)

The committed `pyproject.toml` must **not** contain `[tool.uv.sources]`. End users install
`bengal-chirp`, `chirp-ui`, and `kida-templates` from **PyPI** via normal `pip install sunwell` /
`uv sync`.

If you develop Sunwell inside the **b-stack monorepo** and want editable local packages:

1. `cp .dev-sources.toml.example .dev-sources.toml` and fix paths if your layout differs.
2. `uv run python scripts/dev_sync.py --all-extras` (or add the sync flags you use).

That injects `[tool.uv.sources]` into your working `pyproject.toml` and refreshes the venv.

Before opening a PR, drop local overrides and PyPI-resolve the lockfile:

```bash
git checkout pyproject.toml uv.lock
uv sync --all-extras
```

Do not commit `.dev-sources.toml` (it is gitignored).
