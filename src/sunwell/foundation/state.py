"""Central state directory resolution.

Decouples Sunwell's runtime state from the workspace source tree.
Every subsystem that needs to read/write state should call
``resolve_state_dir()`` instead of constructing ``.sunwell/`` paths
inline.

Moved from sunwell.knowledge.project.state to foundation since this
is a pure-stdlib utility with no knowledge-layer dependencies.

Resolution precedence:
  1. ``SUNWELL_STATE_DIR`` environment variable (absolute override)
  2. ``state_dir`` field in ``.sunwell/project.toml`` manifest
  3. Legacy default: ``{workspace}/.sunwell/``
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Subdirectories that hold generated/ephemeral state (movable out-of-tree).
STATE_SUBDIRS: tuple[str, ...] = (
    "awareness",
    "backlog",
    "checkpoints",
    "external",
    "index",
    "intelligence",
    "logs",
    "memory",
    "metrics",
    "plans",
    "recovery",
    "sessions",
    "snapshots",
    "state",
    "team",
    "worktrees",
)

# Subdirectories/files that should stay in-tree (user-facing, versionable).
IN_TREE_ITEMS: tuple[str, ...] = (
    "project.toml",
    "config.yaml",
    "config.toml",
    "hooks.toml",
    "lenses",
)


def xdg_data_home() -> Path:
    """Return the XDG data home directory.

    Uses ``$XDG_DATA_HOME`` if set, otherwise falls back to
    platform-appropriate defaults:
      - Linux/macOS: ``~/.local/share``
      - Windows: ``%LOCALAPPDATA%`` or ``~/AppData/Local``
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg)

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"

    return Path.home() / ".local" / "share"


def default_state_root() -> Path:
    """Default root for all out-of-tree project state.

    Returns ``$XDG_DATA_HOME/sunwell/projects/``.
    """
    return xdg_data_home() / "sunwell" / "projects"


def resolve_state_dir(workspace: Path) -> Path:
    """Resolve the state directory for a workspace.

    Precedence:

    1. ``SUNWELL_STATE_DIR`` env var -- absolute override for the
       entire state tree.  Useful for CI, containers, or testing.
    2. ``state_dir`` field in the workspace's ``.sunwell/project.toml``
       manifest -- per-project override set at init time.
    3. Legacy default -- ``{workspace}/.sunwell/``.

    The returned path is always absolute and resolved.

    Args:
        workspace: Absolute path to the workspace root (where source lives).

    Returns:
        Absolute path to the directory where runtime state should be stored.
    """
    workspace = workspace.resolve()

    # 1. Environment variable (absolute override)
    env = os.environ.get("SUNWELL_STATE_DIR", "").strip()
    if env:
        p = Path(env).resolve()
        logger.debug("State dir from SUNWELL_STATE_DIR: %s", p)
        return p

    # 2. Manifest state_dir field
    manifest_state = _read_manifest_state_dir(workspace)
    if manifest_state is not None:
        p = Path(manifest_state)
        if not p.is_absolute():
            # Relative paths are resolved against the workspace root
            p = (workspace / p).resolve()
        else:
            p = p.resolve()
        logger.debug("State dir from manifest: %s", p)
        return p

    # 3. Legacy default: in-tree .sunwell/
    return workspace / ".sunwell"


def _read_manifest_state_dir(workspace: Path) -> str | None:
    """Read ``state_dir`` from .sunwell/project.toml if it exists.

    Returns None if the manifest doesn't exist, can't be parsed,
    or doesn't have a ``state_dir`` field.
    """
    manifest_path = workspace / ".sunwell" / "project.toml"
    if not manifest_path.exists():
        return None

    try:
        import tomllib

        content = manifest_path.read_text(encoding="utf-8")
        data = tomllib.loads(content)
        state_section = data.get("state", {})
        return state_section.get("dir")
    except Exception:
        return None


def ensure_state_dir(workspace: Path) -> Path:
    """Resolve and create the state directory if it doesn't exist.

    Convenience wrapper around :func:`resolve_state_dir` that also
    ``mkdir``s the directory.

    Args:
        workspace: Absolute path to the workspace root.

    Returns:
        The (now existing) state directory path.
    """
    state = resolve_state_dir(workspace)
    state.mkdir(parents=True, exist_ok=True)
    return state
