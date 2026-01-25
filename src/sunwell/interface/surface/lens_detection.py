"""Lens Detection — Auto-detect appropriate lens for project (RFC-086, RFC-100).

This module provides intelligent lens selection based on project structure,
extending the base domain detection with more granular marker-based refinement.

RFC-100 expanded domain coverage from 4 to 12 domains with specialized lenses.
"""

from pathlib import Path

from sunwell.interface.surface.fallback import get_domain_for_project

# =============================================================================
# DOMAIN → LENS MAPPING (RFC-100: Expanded from 4 to 12 domains)
# =============================================================================

# Base domain to lens mapping
DOMAIN_LENS_MAP: dict[str, str] = {
    # Original domains
    "documentation": "tech-writer.lens",
    "software": "coder.lens",
    "planning": "team-pm.lens",
    "data": "data-pipeline-expert.lens",
    # New domains from RFC-100
    "security": "security-auditor.lens",
    "devops": "docker-expert.lens",
    "ml": "ml-experimenter.lens",
    "testing": "test-writer.lens",
    "api": "api-documenter.lens",
}

# Documentation-specific markers for lens refinement
DOC_MARKERS: dict[str, str] = {
    # Documentation frameworks → tech-writer or specialized
    "fern/": "tech-writer.lens",
    "docusaurus.config.js": "tech-writer.lens",
    "mkdocs.yml": "tech-writer.lens",
    "conf.py": "sphinx-expert.lens",  # Sphinx-specific
    "antora.yml": "tech-writer.lens",
    "book.toml": "tech-writer.lens",  # mdBook
    ".vitepress/": "tech-writer.lens",
    # API documentation (RFC-100)
    "openapi.yaml": "api-documenter.lens",
    "openapi.json": "api-documenter.lens",
    "swagger.yaml": "api-documenter.lens",
    "swagger.json": "api-documenter.lens",
    # README focus
    "README.md": "readme-crafter.lens",
    # Changelog focus
    "CHANGELOG.md": "changelog-writer.lens",
    # Tutorial content
    "tutorials/": "tutorial-writer.lens",
    "getting-started/": "tutorial-writer.lens",
    # Fiction markers
    "novel.md": "novelist.lens",
    "manuscript/": "novelist.lens",
    "chapters/": "novelist.lens",
    "scenes/": "novelist.lens",
    ".scrivener": "novelist.lens",
    # Research/academic markers
    "bibliography.bib": "academic-writer.lens",
    "references.bib": "academic-writer.lens",
    ".tex": "academic-writer.lens",
    # Legal markers
    "contracts/": "legal-writer.lens",
    "legal/": "legal-writer.lens",
}

# Software-specific markers for lens refinement (RFC-100: Language detection)
SOFTWARE_MARKERS: dict[str, str] = {
    # Python projects
    "pyproject.toml": "python-expert.lens",
    "setup.py": "python-expert.lens",
    "ruff.toml": "python-expert.lens",
    # TypeScript projects
    "tsconfig.json": "typescript-expert.lens",
    # Go projects
    "go.mod": "go-expert.lens",
    # Rust projects
    "Cargo.toml": "rust-expert.lens",
    # Testing-focused (RFC-100)
    "pytest.ini": "test-writer.lens",
    "conftest.py": "test-writer.lens",
    "cypress/": "e2e-test-writer.lens",
    "playwright.config.ts": "e2e-test-writer.lens",
    "playwright.config.js": "e2e-test-writer.lens",
    ".coveragerc": "coverage-analyst.lens",
    # Security-focused (RFC-100)
    "security/": "security-auditor.lens",
    ".gitleaks.toml": "security-auditor.lens",
    "trufflehog.yaml": "security-auditor.lens",
    # DevOps-focused (RFC-100)
    "Dockerfile": "docker-expert.lens",
    "docker-compose.yml": "docker-expert.lens",
    "kubernetes/": "kubernetes-expert.lens",
    ".github/workflows/": "github-actions-expert.lens",
    "terraform/": "terraform-expert.lens",
    # ML/Data-focused (RFC-100)
    "notebooks/": "notebook-reviewer.lens",
    "*.ipynb": "notebook-reviewer.lens",
    "mlflow/": "ml-ops-expert.lens",
    "dbt_project.yml": "dbt-expert.lens",
    # QA-focused
    "test/": "test-writer.lens",
    "tests/": "test-writer.lens",
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
