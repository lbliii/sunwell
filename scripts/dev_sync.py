#!/usr/bin/env python3
"""Merge .dev-sources.toml into pyproject.toml and run uv sync (local monorepo dev).

Committed pyproject.toml must not contain [tool.uv.sources] so pip/uv installs from
PyPI work for end users. Optional .dev-sources.toml (gitignored) lists editable paths.

Usage:
  uv run python scripts/dev_sync.py --all-extras
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path


def _extract_sources_block(content: str) -> str | None:
    match = re.search(
        r"\[tool\.uv\.sources\]\s*\n(.*?)(?=\n\[|\Z)",
        content,
        re.DOTALL,
    )
    return match.group(0).strip() if match else None


def _inject_sources(pyproject: str, sources_block: str) -> str:
    if re.search(r"\n\[tool\.uv\.sources\]\s*\n", pyproject):
        return re.sub(
            r"\n\[tool\.uv\.sources\].*?(?=\n\[[a-z#]|\Z)",
            "\n" + sources_block + "\n\n",
            pyproject,
            count=1,
            flags=re.DOTALL,
        )
    return pyproject.replace(
        "\n[tool.ruff]",
        "\n" + sources_block + "\n\n[tool.ruff]",
    )


def _local_source_sync_args(dev_sources: Path, base_args: list[str]) -> list[str]:
    sync_args = list(base_args) if "--no-cache" in base_args else [*base_args, "--no-cache"]
    parsed = tomllib.loads(dev_sources.read_text())
    source_table = parsed.get("tool", {}).get("uv", {}).get("sources", {})
    for package_name in source_table:
        sync_args.extend(
            [
                "--refresh-package",
                package_name,
                "--reinstall-package",
                package_name,
            ]
        )
    return sync_args


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    pyproject_path = root / "pyproject.toml"
    dev_sources = root / ".dev-sources.toml"
    uv_sync_args = sys.argv[1:]

    if not dev_sources.exists():
        subprocess.run(["uv", "sync", *uv_sync_args], cwd=root, check=True)
        return 0

    sources_block = _extract_sources_block(dev_sources.read_text())
    if not sources_block:
        subprocess.run(["uv", "sync", *uv_sync_args], cwd=root, check=True)
        return 0

    orig = pyproject_path.read_text()
    modified = _inject_sources(orig, sources_block)
    pyproject_path.write_text(modified)
    subprocess.run(
        ["uv", "sync", *_local_source_sync_args(dev_sources, uv_sync_args)],
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
