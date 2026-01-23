"""Project type detection for content-aware indexing (RFC-108).

Sunwell automatically detects project type and adapts its indexing strategy:
- CODE: AST-aware chunking for functions/classes
- PROSE: Paragraph/section-aware chunking for narrative flow
- SCRIPT: Scene-aware chunking for screenplays
- DOCS: Heading-aware chunking for documentation
- MIXED: Per-file detection
"""

from enum import Enum
from pathlib import Path


class ProjectType(Enum):
    """Project type classification."""

    CODE = "code"
    PROSE = "prose"
    SCRIPT = "script"
    DOCS = "docs"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# Marker files/directories that indicate project type
PROJECT_MARKERS: dict[ProjectType, list[str]] = {
    ProjectType.CODE: [
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "setup.py",
        "pom.xml",
        "build.gradle",
        "*.csproj",
        "*.sln",
        "src/",
        "lib/",
    ],
    ProjectType.PROSE: [
        "manuscript/",
        "chapters/",
        "novel.md",
        "story.md",
        "*.scriv",
        "draft/",
        "writing/",
    ],
    ProjectType.SCRIPT: [
        "*.fountain",
        "*.fdx",
        "screenplay/",
        "script/",
        "*.highland",
        "teleplay/",
    ],
    ProjectType.DOCS: [
        "docs/",
        "documentation/",
        "conf.py",
        "mkdocs.yml",
        "docusaurus.config.js",
        ".readthedocs.yml",
        "antora.yml",
    ],
}


# Extensions by content type
CODE_EXTENSIONS = frozenset({
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".swift",
    ".rb",
    ".php",
})

SCRIPT_EXTENSIONS = frozenset({
    ".fountain",
    ".fdx",
    ".highland",
})


def detect_project_type(workspace_root: Path) -> ProjectType:
    """Detect project type from marker files.

    Returns the dominant type, or MIXED if multiple types detected.

    Args:
        workspace_root: Root directory of the workspace.

    Returns:
        Detected ProjectType.
    """
    detected: set[ProjectType] = set()

    for ptype, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                if list(workspace_root.glob(marker)):
                    detected.add(ptype)
            elif (workspace_root / marker).exists():
                detected.add(ptype)

    if len(detected) == 0:
        return ProjectType.UNKNOWN
    if len(detected) == 1:
        return detected.pop()
    if len(detected) > 1:
        return ProjectType.MIXED

    return ProjectType.UNKNOWN


def detect_file_type(file_path: Path) -> ProjectType:
    """Detect content type for a single file.

    Used in MIXED projects to choose the right chunker.

    Args:
        file_path: Path to the file.

    Returns:
        Detected ProjectType for this file.
    """
    ext = file_path.suffix.lower()

    if ext in CODE_EXTENSIONS:
        return ProjectType.CODE
    if ext in SCRIPT_EXTENSIONS:
        return ProjectType.SCRIPT

    # For .md/.txt, check content patterns
    if ext in {".md", ".txt"}:
        try:
            content = file_path.read_text()[:2000]  # First 2KB

            # Screenplay markers
            if "INT." in content or "EXT." in content or "FADE IN:" in content:
                return ProjectType.SCRIPT

            # Documentation markers
            if "```" in content or "##" in content[:500]:
                return ProjectType.DOCS

            # Default prose for plain text
            return ProjectType.PROSE
        except Exception:
            return ProjectType.DOCS

    return ProjectType.DOCS  # Default for unknown
