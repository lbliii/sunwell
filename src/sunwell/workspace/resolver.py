"""Workspace resolution with confirmation and defaults (RFC-043 addendum).

Provides unified workspace resolution logic for both CLI and Desktop:
- Sensible defaults (~/.sunwell/projects/)
- Explicit path override
- Detection from cwd
- Confirmation prompts for ambiguous situations
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ResolutionSource(Enum):
    """How the workspace was resolved."""

    EXPLICIT = "explicit"  # User provided --workspace or path
    ENVIRONMENT = "environment"  # SUNWELL_WORKSPACE env var
    DETECTED = "detected"  # Found project markers in cwd or parent
    DEFAULT = "default"  # Using default ~/Sunwell/projects/


@dataclass(frozen=True, slots=True)
class WorkspaceResult:
    """Result of workspace resolution."""

    path: Path
    """Resolved workspace path."""

    source: ResolutionSource
    """How the workspace was found."""

    confidence: float
    """Confidence in the resolution (0.0-1.0).

    High confidence (>= 0.9): Proceed without confirmation
    Low confidence (< 0.9): Should confirm with user in interactive mode
    """

    project_name: str | None = None
    """Derived project name (for new projects)."""

    exists: bool = False
    """Whether the path already exists."""

    @property
    def needs_confirmation(self) -> bool:
        """Whether this resolution should be confirmed with user."""
        return self.confidence < 0.9


# Project markers that indicate a valid project root
PROJECT_MARKERS = (
    ".sunwell",  # Explicit Sunwell project
    "pyproject.toml",  # Python
    "package.json",  # Node
    "Cargo.toml",  # Rust
    "go.mod",  # Go
    ".git",  # Git repository
    "setup.py",  # Legacy Python
    "Makefile",  # C/C++ or general
)


def default_workspace_root() -> Path:
    """Get platform-appropriate default workspace root.

    Returns:
        ~/Sunwell/projects/ on all platforms
    """
    return Path.home() / "Sunwell" / "projects"


def default_config_root() -> Path:
    """Get platform-appropriate config root.

    Returns:
        ~/Sunwell/.sunwell/ for global config
    """
    return Path.home() / "Sunwell" / ".sunwell"


def _find_project_root(start: Path) -> Path | None:
    """Walk up from start looking for project markers.

    Args:
        start: Directory to start searching from

    Returns:
        Path to project root if found, None otherwise
    """
    current = start.resolve()

    # Don't walk above home directory
    home = Path.home()

    while current != current.parent:
        # Stop at home directory
        if current == home:
            break

        # Check for project markers
        for marker in PROJECT_MARKERS:
            if (current / marker).exists():
                return current

        current = current.parent

    return None


def _is_empty_or_random(path: Path) -> bool:
    """Check if path looks like a random/temporary location.

    These locations should trigger confirmation:
    - /tmp, /var/tmp
    - Downloads folder
    - Desktop (maybe user wants it there, but confirm)
    - Root directories
    """
    path_str = str(path.resolve()).lower()

    random_indicators = [
        "/tmp",
        "/var/tmp",
        "/temp",
        "downloads",
        "/private/tmp",  # macOS
    ]

    return any(indicator in path_str for indicator in random_indicators)


def resolve_workspace(
    explicit: Path | str | None = None,
    start: Path | None = None,
    project_name: str | None = None,
) -> WorkspaceResult:
    """Resolve workspace with full context about how it was found.

    Resolution precedence:
    1. Explicit path (--workspace flag or direct argument)
    2. SUNWELL_WORKSPACE environment variable
    3. Current directory if it has project markers
    4. Walk up to find nearest project root
    5. Default ~/Sunwell/projects/

    Args:
        explicit: Explicit path from user (--workspace or argument)
        start: Starting directory for detection (defaults to cwd)
        project_name: Name for new project (used with default workspace)

    Returns:
        WorkspaceResult with path, source, and confidence
    """
    # 1. Explicit always wins
    if explicit:
        path = Path(explicit).resolve()
        return WorkspaceResult(
            path=path,
            source=ResolutionSource.EXPLICIT,
            confidence=1.0,
            exists=path.exists(),
        )

    # 2. Environment variable
    env_ws = os.environ.get("SUNWELL_WORKSPACE")
    if env_ws:
        path = Path(env_ws).resolve()
        return WorkspaceResult(
            path=path,
            source=ResolutionSource.ENVIRONMENT,
            confidence=1.0,
            exists=path.exists(),
        )

    # 3. Detect from cwd or walk up
    start = (start or Path.cwd()).resolve()

    # Check if cwd itself has project markers
    found = _find_project_root(start)

    if found:
        return WorkspaceResult(
            path=found,
            source=ResolutionSource.DETECTED,
            confidence=0.95,
            exists=True,
        )

    # 4. Check if cwd looks random/temporary
    if _is_empty_or_random(start):
        # Definitely use default, but low confidence
        default_path = default_workspace_root()
        if project_name:
            default_path = default_path / _slugify(project_name)

        return WorkspaceResult(
            path=default_path,
            source=ResolutionSource.DEFAULT,
            confidence=0.3,  # Very low - definitely confirm
            project_name=project_name,
            exists=default_path.exists(),
        )

    # 5. No project found, use default
    default_path = default_workspace_root()
    if project_name:
        default_path = default_path / _slugify(project_name)

    return WorkspaceResult(
        path=default_path,
        source=ResolutionSource.DEFAULT,
        confidence=0.5,  # Low - should confirm
        project_name=project_name,
        exists=default_path.exists(),
    )


def _slugify(name: str) -> str:
    """Convert project name to directory-safe slug.

    Examples:
        "Forum App" → "forum-app"
        "My REST API" → "my-rest-api"
        "The Lighthouse Keeper" → "the-lighthouse-keeper"
    """
    import re

    # Lowercase
    slug = name.lower()

    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    return slug or "project"


def ensure_workspace_exists(result: WorkspaceResult) -> Path:
    """Ensure the workspace directory exists.

    Creates the directory structure if needed.

    Args:
        result: Resolved workspace result

    Returns:
        The workspace path (now guaranteed to exist)
    """
    result.path.mkdir(parents=True, exist_ok=True)

    # Create .sunwell subdirectory for project config
    sunwell_dir = result.path / ".sunwell"
    sunwell_dir.mkdir(exist_ok=True)

    return result.path


def format_resolution_message(result: WorkspaceResult) -> str:
    """Format a human-readable message about workspace resolution.

    Args:
        result: Resolved workspace result

    Returns:
        Message suitable for CLI output
    """
    path_str = str(result.path)

    # Shorten home directory
    home = str(Path.home())
    if path_str.startswith(home):
        path_str = "~" + path_str[len(home) :]

    match result.source:
        case ResolutionSource.EXPLICIT:
            return f"Working in: {path_str}"
        case ResolutionSource.ENVIRONMENT:
            return f"Working in: {path_str} (from SUNWELL_WORKSPACE)"
        case ResolutionSource.DETECTED:
            name = result.path.name
            return f"Working in: {name} ({path_str})"
        case ResolutionSource.DEFAULT:
            return f"Creating project in: {path_str}"
