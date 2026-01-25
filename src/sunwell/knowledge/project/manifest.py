"""Manifest loader for .sunwell/project.toml (RFC-117).

Handles reading and writing project manifests.
"""

import tomllib
from datetime import datetime
from pathlib import Path

from sunwell.knowledge.project.types import AgentConfig, ProjectManifest


class ManifestError(Exception):
    """Raised when manifest loading/saving fails."""


def load_manifest(path: Path) -> ProjectManifest:
    """Load project manifest from .sunwell/project.toml.

    Args:
        path: Path to project.toml file

    Returns:
        Parsed ProjectManifest

    Raises:
        ManifestError: If file is missing or invalid
    """
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
        data = tomllib.loads(content)
        return ProjectManifest.from_dict(data)
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"Invalid TOML in {path}: {e}") from e
    except (KeyError, ValueError, TypeError) as e:
        raise ManifestError(f"Invalid manifest structure in {path}: {e}") from e


def save_manifest(manifest: ProjectManifest, path: Path) -> None:
    """Save project manifest to .sunwell/project.toml.

    Args:
        manifest: Manifest to save
        path: Path to project.toml file
    """
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to TOML format
    content = _format_toml(manifest.to_dict())
    path.write_text(content, encoding="utf-8")


def create_manifest(
    project_id: str,
    name: str | None = None,
    trust: str = "workspace",
    protected: list[str] | None = None,
) -> ProjectManifest:
    """Create a new project manifest.

    Args:
        project_id: Unique identifier for the project
        name: Human-readable name (defaults to id)
        trust: Default trust level
        protected: Paths to protect from agent modification

    Returns:
        New ProjectManifest instance
    """
    return ProjectManifest(
        id=project_id,
        name=name or project_id,
        created=datetime.now(),
        workspace_type="existing",
        agent=AgentConfig(
            trust=trust,
            protected=tuple(protected or [".git"]),
        ),
    )


def _format_toml(data: dict) -> str:
    """Format dict as TOML string.

    Simple formatter since tomllib is read-only.
    """
    lines = ["# Sunwell Project Manifest", "# See RFC-117 for details", ""]

    # [project] section
    project = data.get("project", {})
    lines.append("[project]")
    lines.append(f'id = "{project.get("id", "")}"')
    lines.append(f'name = "{project.get("name", "")}"')
    lines.append(f'created = "{project.get("created", "")}"')
    lines.append("")

    # [workspace] section
    workspace = data.get("workspace", {})
    lines.append("[workspace]")
    lines.append(f'type = "{workspace.get("type", "existing")}"')
    lines.append("")

    # [agent] section
    agent = data.get("agent", {})
    lines.append("[agent]")
    lines.append(f'trust = "{agent.get("trust", "workspace")}"')

    # Format protected list
    protected = agent.get("protected", [])
    if protected:
        protected_str = ", ".join(f'"{p}"' for p in protected)
        lines.append(f"protected = [{protected_str}]")
    else:
        lines.append("protected = []")

    lines.append("")
    return "\n".join(lines)
