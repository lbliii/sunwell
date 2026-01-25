"""Project discovery for User Environment Model (RFC-104).

Discovers project roots and projects using the existing WorkspaceDetector.
This module provides multi-project awareness on top of single-project detection.
"""

from datetime import datetime
from pathlib import Path

from sunwell.knowledge.environment.model import ProjectEntry, ProjectRoot
from sunwell.knowledge.workspace.detector import WorkspaceDetector

# =============================================================================
# Constants
# =============================================================================

MAX_SCAN_DEPTH = 2
"""How deep to scan for projects (e.g., ~/github/python/* but not deeper)."""

MIN_PROJECTS_FOR_ROOT = 2
"""Minimum projects needed to consider a directory a "root"."""

# Common locations where users keep projects
DEFAULT_ROOT_CANDIDATES = (
    "Documents/github",
    "Documents/gitlab",
    "Documents/bitbucket",
    "Documents/projects",
    "projects",
    "code",
    "dev",
    "src",
    "workspace",
    "work",
    "repos",
    "git",
    "github",
    "gitlab",
)


# =============================================================================
# Discovery Functions
# =============================================================================


def discover_roots(home: Path | None = None) -> list[ProjectRoot]:
    """Find directories that contain multiple projects.

    Scans known candidate directories under the user's home to find
    locations containing multiple projects.

    Args:
        home: Home directory to scan from. Defaults to Path.home().

    Returns:
        List of ProjectRoot objects for directories containing projects.
    """
    home = (home or Path.home()).resolve()
    detector = WorkspaceDetector()
    roots: list[ProjectRoot] = []

    # Build candidate paths
    candidates = [home / candidate for candidate in DEFAULT_ROOT_CANDIDATES]

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_dir():
            continue

        # Find projects under this candidate
        projects = _find_projects_in_directory(candidate, detector, MAX_SCAN_DEPTH)

        if len(projects) >= MIN_PROJECTS_FOR_ROOT:
            primary_type = _infer_primary_type(projects)
            roots.append(
                ProjectRoot(
                    path=candidate,
                    discovered_at=datetime.now(),
                    project_count=len(projects),
                    primary_type=primary_type,
                    scan_frequency=_infer_scan_frequency(projects),
                )
            )

    return roots


def discover_projects_in_root(root: Path) -> list[ProjectEntry]:
    """Discover all projects under a given root directory.

    Identifies project directories by looking for project markers
    (pyproject.toml, package.json, .git, etc.).

    Args:
        root: Root directory to scan.

    Returns:
        List of ProjectEntry objects for discovered projects.
    """
    detector = WorkspaceDetector()  # For marker list only
    project_paths = _find_projects_in_directory(root.resolve(), detector, MAX_SCAN_DEPTH)

    entries: list[ProjectEntry] = []
    for path in project_paths:
        entry = _create_project_entry(path)
        if entry:
            entries.append(entry)

    return entries


def create_project_entry_from_path(path: Path) -> ProjectEntry | None:
    """Create a ProjectEntry from a single path.

    Useful when adding a known project to the environment.

    Args:
        path: Path to the project directory.

    Returns:
        ProjectEntry if the path is a valid project, None otherwise.
    """
    return _create_project_entry(path.resolve())


# =============================================================================
# Internal Helpers
# =============================================================================


MAX_PROJECTS_PER_ROOT = 100
"""Maximum projects to discover per root to prevent runaway scans."""

SKIP_DIRECTORIES = frozenset({
    "node_modules", "vendor", ".venv", "venv", "__pycache__",
    "dist", "build", ".tox", "target", ".git", ".hg", ".svn",
    "cache", ".cache", "Cache", ".npm", ".cargo", ".rustup",
})
"""Directories to skip during discovery."""


def _find_projects_in_directory(
    root: Path,
    detector: WorkspaceDetector,
    max_depth: int,
    _count: list | None = None,
) -> list[Path]:
    """Find project directories within root, respecting depth limit.

    Args:
        root: Directory to scan.
        detector: WorkspaceDetector instance.
        max_depth: Maximum depth to recurse.
        _count: Internal counter to limit total projects.

    Returns:
        List of paths that are project roots.
    """
    if _count is None:
        _count = [0]

    projects: list[Path] = []

    if max_depth <= 0 or _count[0] >= MAX_PROJECTS_PER_ROOT:
        return projects

    try:
        for path in root.iterdir():
            if _count[0] >= MAX_PROJECTS_PER_ROOT:
                break

            if not path.is_dir():
                continue

            # Skip hidden and known heavy directories
            if path.name.startswith(".") or path.name in SKIP_DIRECTORIES:
                continue

            # Check if this directory is a project
            if _is_project_directory(path, detector):
                projects.append(path)
                _count[0] += 1
            # Otherwise, recurse if depth allows
            elif max_depth > 1:
                projects.extend(
                    _find_projects_in_directory(path, detector, max_depth - 1, _count)
                )

    except (PermissionError, OSError):
        pass  # Skip inaccessible directories

    return projects


def _is_project_directory(path: Path, detector: WorkspaceDetector) -> bool:
    """Check if a directory is a project root.

    A directory is considered a project if it:
    - Has a .git directory
    - Has a .sunwell directory
    - Has any of the standard project markers

    Args:
        path: Directory to check.
        detector: WorkspaceDetector instance.

    Returns:
        True if the directory is a project root.
    """
    # Quick checks for common markers
    if (path / ".git").is_dir():
        return True
    if (path / ".sunwell").is_dir():
        return True

    # Check for project markers
    for marker in detector.PROJECT_MARKERS:
        if "*" in marker:
            if list(path.glob(marker)):
                return True
        elif (path / marker).exists():
            return True

    return False


def _create_project_entry(path: Path) -> ProjectEntry | None:
    """Create a ProjectEntry from a path.

    Uses simple filesystem checks for fast discovery.

    Args:
        path: Path to the project.

    Returns:
        ProjectEntry if valid, None otherwise.
    """
    try:
        project_type = _infer_project_type(path)
        name = path.name
        is_git = (path / ".git").is_dir()

        return ProjectEntry(
            path=path,
            name=name,
            project_type=project_type,
            health_score=None,
            last_scanned=None,
            is_reference=False,
            tags=(),
            is_git=is_git,
        )
    except Exception:
        return None


def _infer_project_type(path: Path) -> str:
    """Infer project type from filesystem markers.

    Uses marker files only - no recursive globbing for performance.

    Args:
        path: Project root path.

    Returns:
        Project type string: "python", "docs", "go", "node", "rust", or "unknown".
    """
    # Documentation projects
    doc_markers = ["conf.py", "mkdocs.yml", "docusaurus.config.js", "book.toml", "_quarto.yml"]
    for marker in doc_markers:
        if (path / marker).exists():
            return "docs"

    # Language-specific markers
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return "python"
    if (path / "go.mod").exists():
        return "go"
    if (path / "Cargo.toml").exists():
        return "rust"
    if (path / "package.json").exists():
        return "node"
    if (path / "pom.xml").exists() or (path / "build.gradle").exists():
        return "java"

    # Check for src/ directory with common extensions (shallow check only)
    src_dir = path / "src"
    if src_dir.is_dir():
        try:
            # Quick shallow check - just look at immediate children of src/
            for child in list(src_dir.iterdir())[:20]:
                if child.suffix == ".py":
                    return "python"
                if child.suffix == ".go":
                    return "go"
                if child.suffix in (".js", ".ts"):
                    return "node"
        except (PermissionError, OSError):
            pass

    return "unknown"


def _infer_primary_type(projects: list[Path]) -> str:
    """Infer the primary project type for a collection of projects.

    Args:
        projects: List of project paths.

    Returns:
        Primary type string or "mixed" if no dominant type.
    """
    type_counts: dict[str, int] = {}
    for path in projects:
        ptype = _infer_project_type(path)
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

    if not type_counts:
        return "mixed"

    # Find dominant type (>50% of projects)
    total = len(projects)
    for ptype, count in type_counts.items():
        if count > total * 0.5:
            return ptype

    return "mixed"


def _infer_scan_frequency(projects: list[Path]) -> str:
    """Infer how often projects in this root change.

    Based on git commit recency if available.

    Args:
        projects: List of project paths.

    Returns:
        "often", "sometimes", or "rarely".
    """
    import subprocess
    from datetime import timedelta

    recent_count = 0
    checked_count = 0
    now = datetime.now()

    for path in projects[:10]:  # Sample up to 10 projects
        if not (path / ".git").is_dir():
            continue

        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                commit_time = datetime.fromtimestamp(int(result.stdout.strip()))
                if now - commit_time < timedelta(days=30):
                    recent_count += 1
                checked_count += 1
        except (subprocess.TimeoutExpired, ValueError, OSError):
            continue

    if checked_count == 0:
        return "sometimes"

    ratio = recent_count / checked_count
    if ratio > 0.5:
        return "often"
    elif ratio > 0.2:
        return "sometimes"
    else:
        return "rarely"
