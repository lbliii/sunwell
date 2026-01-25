"""Priority file detection for fast initial indexing (RFC-108).

Index hot files first so the index is useful within seconds,
then continue with the full index in background.

Priority files vary by project type:
- Code: README, entry points, config files
- Prose: outline, characters, first chapters
- Scripts: treatment, beat sheet, script file
- Docs: index, getting-started, overview
"""

import subprocess
from pathlib import Path

from sunwell.knowledge.indexing.project_type import ProjectType

# Files to always index first (glob patterns) by project type
PRIORITY_PATTERNS: dict[ProjectType, list[str]] = {
    ProjectType.CODE: [
        # Documentation
        "README*",
        "CONTRIBUTING*",
        "CHANGELOG*",
        # Config
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        # Entry points
        "src/*/main.py",
        "src/*/__main__.py",
        "src/index.ts",
        "src/main.ts",
        "main.go",
        "cmd/*/main.go",
        "src/main.rs",
        "src/lib.rs",
        # CLI
        "src/*/cli.py",
        "src/*/cli/*.py",
        "cli/*.py",
    ],
    ProjectType.PROSE: [
        # Planning
        "outline*",
        "synopsis*",
        "treatment*",
        # Characters
        "characters*",
        "cast*",
        "dramatis*",
        # World
        "world*",
        "setting*",
        "locations*",
        # Recent chapters (glob by number)
        "chapters/[0-9][0-9]-*.md",
        "manuscript/[0-9][0-9]-*.md",
    ],
    ProjectType.SCRIPT: [
        # Planning
        "outline*",
        "treatment*",
        "beat-sheet*",
        # Character
        "characters*",
        "cast*",
        # The script itself
        "*.fountain",
        "*.fdx",
        "script.*",
    ],
    ProjectType.DOCS: [
        # Navigation
        "index.md",
        "README.md",
        "overview*",
        # Getting started
        "get-started*",
        "quickstart*",
        "installation*",
        # Config
        "conf.py",
        "mkdocs.yml",
        "_config.yml",
    ],
}

# Default patterns for unknown/mixed projects
DEFAULT_PRIORITY_PATTERNS = [
    "README*",
    "CONTRIBUTING*",
    "CHANGELOG*",
    "docs/index.*",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "src/*/main.py",
    "src/*/__main__.py",
    "src/index.ts",
    "main.go",
    "src/main.rs",
    "src/lib.rs",
]


def get_priority_files(
    workspace_root: Path,
    project_type: ProjectType | None = None,
    max_files: int = 200,
) -> list[Path]:
    """Get files to index first for fast startup.

    Returns files in priority order:
    1. Pattern-matched priority files (based on project type)
    2. Recently modified files (from git)
    3. Capped at max_files for fast startup

    Args:
        workspace_root: Root directory of the workspace.
        project_type: Detected project type (uses defaults if None).
        max_files: Maximum number of priority files to return.

    Returns:
        List of priority file paths.
    """
    priority_files: list[Path] = []
    seen: set[Path] = set()

    # Get patterns for this project type
    if project_type and project_type in PRIORITY_PATTERNS:
        patterns = PRIORITY_PATTERNS[project_type]
    else:
        patterns = DEFAULT_PRIORITY_PATTERNS

    # 1. Pattern-matched files
    for pattern in patterns:
        for path in workspace_root.glob(pattern):
            if path.is_file() and path not in seen:
                priority_files.append(path)
                seen.add(path)

    # 2. Recently modified files (git log)
    recent = _get_recently_modified(workspace_root)
    for path in recent:
        if path not in seen:
            priority_files.append(path)
            seen.add(path)

    # 3. Cap at max_files
    return priority_files[:max_files]


def _get_recently_modified(workspace_root: Path, limit: int = 50) -> list[Path]:
    """Get recently modified files from git log.

    Args:
        workspace_root: Root directory of the workspace.
        limit: Maximum commits to look at.

    Returns:
        List of recently modified file paths.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{limit}", "--name-only", "--pretty=format:"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        files: list[Path] = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                path = workspace_root / line
                if path.exists() and path.is_file():
                    files.append(path)

        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
