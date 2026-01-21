"""Fallback Chain (RFC-072).

Ensures the surface is NEVER empty, even on invalid specs.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.surface.types import SurfaceLayout, SurfacePrimitive, WorkspaceSpec

if TYPE_CHECKING:
    from sunwell.surface.renderer import SurfaceRenderer

# =============================================================================
# DEFAULT LAYOUTS
# =============================================================================

# Universal default when nothing else works
DEFAULT_LAYOUT = SurfaceLayout(
    primary=SurfacePrimitive(
        id="CodeEditor",
        category="code",
        size="full",
    ),
    secondary=(SurfacePrimitive(id="FileTree", category="code", size="sidebar"),),
    contextual=(),
    arrangement="standard",
)

# Domain-specific defaults
DOMAIN_DEFAULTS: dict[str, SurfaceLayout] = {
    "software": SurfaceLayout(
        primary=SurfacePrimitive(id="CodeEditor", category="code", size="full"),
        secondary=(SurfacePrimitive(id="FileTree", category="code", size="sidebar"),),
        contextual=(),
        arrangement="standard",
    ),
    "documentation": SurfaceLayout(
        primary=SurfacePrimitive(id="ProseEditor", category="writing", size="full"),
        secondary=(SurfacePrimitive(id="Outline", category="writing", size="sidebar"),),
        contextual=(),
        arrangement="standard",
    ),
    "planning": SurfaceLayout(
        primary=SurfacePrimitive(id="Kanban", category="planning", size="full"),
        secondary=(SurfacePrimitive(id="GoalTree", category="planning", size="sidebar"),),
        contextual=(),
        arrangement="standard",
    ),
    "data": SurfaceLayout(
        primary=SurfacePrimitive(id="DataTable", category="data", size="full"),
        secondary=(SurfacePrimitive(id="Chart", category="data", size="panel"),),
        contextual=(),
        arrangement="standard",
    ),
}

# =============================================================================
# FALLBACK CHAIN
# =============================================================================


def render_with_fallback(
    renderer: SurfaceRenderer,
    spec: WorkspaceSpec | None,
    last_successful: SurfaceLayout | None = None,
    project_path: Path | None = None,
) -> SurfaceLayout:
    """Render a spec with guaranteed non-empty result.

    Fallback chain:
    1. Try composition → return if valid
    2. Try last successful layout → return if available
    3. Return domain-specific default
    4. Return universal DEFAULT_LAYOUT

    Args:
        renderer: SurfaceRenderer instance
        spec: Workspace specification (None for fallback only)
        last_successful: Previous successful layout (optional)
        project_path: Project path for domain inference (optional)

    Returns:
        Valid SurfaceLayout (never raises, never returns None)
    """
    # Try the spec first
    if spec is not None:
        try:
            layout = renderer.render(spec)
            if layout and layout.primary:
                return layout
        except (ValueError, KeyError):
            pass  # Fall through to fallback chain

    # Fallback 1: Last successful layout
    if last_successful is not None:
        return last_successful

    # Fallback 2: Domain default based on project files
    if project_path is not None:
        domain_default = _get_domain_default(project_path)
        if domain_default is not None:
            return domain_default

    # Fallback 3: Universal default
    return DEFAULT_LAYOUT


def _get_domain_default(project_path: Path) -> SurfaceLayout | None:
    """Infer domain from project files and return appropriate default.

    Quick heuristics based on marker files present in the project.

    Args:
        project_path: Path to project directory

    Returns:
        Domain-specific default layout, or None if no markers found
    """
    # Marker files → domain mapping
    markers: dict[str, str] = {
        "pyproject.toml": "software",
        "package.json": "software",
        "Cargo.toml": "software",
        "go.mod": "software",
        "setup.py": "software",
        "requirements.txt": "software",
        "docs": "documentation",
        "mkdocs.yml": "documentation",
        "conf.py": "documentation",
        ".kanban": "planning",
        "backlog.md": "planning",
        "ROADMAP.md": "planning",
    }

    for marker, domain in markers.items():
        marker_path = project_path / marker
        if marker_path.exists():
            return DOMAIN_DEFAULTS.get(domain)

    return None


def get_domain_for_project(project_path: Path) -> str:
    """Infer domain from project files.

    Args:
        project_path: Path to project directory

    Returns:
        Domain string: "software", "documentation", "planning", "data", or "software" (default)
    """
    # Marker files → domain mapping
    markers: dict[str, str] = {
        "pyproject.toml": "software",
        "package.json": "software",
        "Cargo.toml": "software",
        "go.mod": "software",
        "docs": "documentation",
        "mkdocs.yml": "documentation",
        ".kanban": "planning",
        "backlog.md": "planning",
    }

    for marker, domain in markers.items():
        if (project_path / marker).exists():
            return domain

    return "software"  # Default
