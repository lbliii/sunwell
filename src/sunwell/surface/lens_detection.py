"""Lens Detection — Auto-detect appropriate lens for project (RFC-086).

This module provides intelligent lens selection based on project structure,
extending the base domain detection with more granular marker-based refinement.
"""

from pathlib import Path

from sunwell.surface.fallback import get_domain_for_project

# =============================================================================
# DOMAIN → LENS MAPPING
# =============================================================================

# Base domain to lens mapping
DOMAIN_LENS_MAP: dict[str, str] = {
    "documentation": "tech-writer.lens",
    "software": "coder.lens",
    "planning": "team-pm.lens",
    "data": "coder.lens",
}

# Documentation-specific markers for lens refinement
DOC_MARKERS: dict[str, str] = {
    # Documentation frameworks
    "fern/": "tech-writer.lens",
    "docusaurus.config.js": "tech-writer.lens",
    "mkdocs.yml": "tech-writer.lens",
    "conf.py": "tech-writer.lens",  # Sphinx
    "antora.yml": "tech-writer.lens",
    "book.toml": "tech-writer.lens",  # mdBook
    ".vitepress/": "tech-writer.lens",
    # Fiction markers
    "novel.md": "novelist.lens",
    "manuscript/": "novelist.lens",
    "chapters/": "novelist.lens",
    "scenes/": "novelist.lens",
    ".scrivener": "novelist.lens",
    # Research/academic markers
    "bibliography.bib": "researcher.lens",
    "references.bib": "researcher.lens",
    ".tex": "researcher.lens",
    # Legal markers
    "contracts/": "legal.lens",
    "legal/": "legal.lens",
}

# Software-specific markers for lens refinement
SOFTWARE_MARKERS: dict[str, str] = {
    # QA-focused projects
    "pytest.ini": "coder.lens",
    "cypress/": "team-qa.lens",
    "playwright.config": "team-qa.lens",
    "test/": "coder.lens",
    "tests/": "coder.lens",
    # Planning-focused
    "roadmap.md": "team-pm.lens",
    "ROADMAP.md": "team-pm.lens",
    "backlog/": "team-pm.lens",
}


def get_lens_for_project(project_path: Path) -> str:
    """Detect appropriate lens from project structure.

    Uses existing domain detection + marker-based refinement for
    more specific lens selection within domains.

    Args:
        project_path: Path to project directory

    Returns:
        Lens filename (e.g., "tech-writer.lens")

    Example:
        >>> get_lens_for_project(Path("~/projects/pachyderm/docs"))
        'tech-writer.lens'
        >>> get_lens_for_project(Path("~/projects/my-novel"))
        'novelist.lens'
    """
    domain = get_domain_for_project(project_path)

    # Apply domain-specific refinement
    if domain == "documentation":
        for marker, lens in DOC_MARKERS.items():
            marker_path = project_path / marker
            if marker_path.exists():
                return lens

    elif domain == "software":
        for marker, lens in SOFTWARE_MARKERS.items():
            marker_path = project_path / marker
            if marker_path.exists():
                return lens

    # Fall back to domain default
    return DOMAIN_LENS_MAP.get(domain, "coder.lens")


def get_mode_for_domain(domain: str) -> str:
    """Map domain to workspace mode.

    Args:
        domain: Domain string from get_domain_for_project

    Returns:
        Mode string: "writer", "code", or "planning"
    """
    return {
        "documentation": "writer",
        "software": "code",
        "planning": "planning",
        "data": "code",
    }.get(domain, "code")


def detect_project_context(project_path: Path) -> dict[str, str]:
    """Full context detection for a project.

    Args:
        project_path: Path to project directory

    Returns:
        Dict with domain, lens, and mode
    """
    domain = get_domain_for_project(project_path)
    lens = get_lens_for_project(project_path)
    mode = get_mode_for_domain(domain)

    return {
        "domain": domain,
        "lens": lens,
        "mode": mode,
        "project_path": str(project_path.resolve()),
    }
