"""Template for .sunwell/.gitignore - RFC-052.

This module provides the gitignore template that should be created when
initializing team intelligence. It ensures proper separation:
- .sunwell/team/ → tracked (shared)
- .sunwell/intelligence/ → ignored (personal)
- .sunwell/personal/ → ignored (personal)
- .sunwell/sessions/ → ignored (conversations)
"""

from pathlib import Path

SUNWELL_GITIGNORE = """\
# Sunwell Directory Structure
# ==========================
# .sunwell/team/        - TRACKED: Shared team knowledge
# .sunwell/intelligence/ - IGNORED: Personal decisions (RFC-045)
# .sunwell/personal/    - IGNORED: Personal preferences
# .sunwell/sessions/    - IGNORED: Conversation history (RFC-013)
# .sunwell/project/     - TRACKED: Auto-generated project analysis

# Personal intelligence (RFC-045) - never shared
intelligence/

# Personal preferences (RFC-052) - never shared
personal/

# Conversation history (RFC-013) - never shared
sessions/

# Embeddings cache - can be regenerated
*.npz
*_embeddings.json

# Python cache
__pycache__/
*.pyc

# Temporary files
*.tmp
*.bak
"""


def create_sunwell_gitignore(sunwell_dir: Path) -> None:
    """Create .gitignore in .sunwell directory.

    Args:
        sunwell_dir: Path to .sunwell directory
    """
    gitignore_path = Path(sunwell_dir) / ".gitignore"

    # Don't overwrite if exists
    if gitignore_path.exists():
        return

    gitignore_path.write_text(SUNWELL_GITIGNORE)


def ensure_sunwell_structure(project_root: Path) -> Path:
    """Ensure .sunwell directory structure exists with proper gitignore.

    Creates:
    - .sunwell/
    - .sunwell/.gitignore
    - .sunwell/team/
    - .sunwell/intelligence/
    - .sunwell/personal/
    - .sunwell/sessions/
    - .sunwell/project/

    Args:
        project_root: Project root directory

    Returns:
        Path to .sunwell directory

    Raises:
        ValueError: If project_root is inside a .sunwell directory
    """
    from pathlib import Path

    project_root = Path(project_root).resolve()

    # Validate we're not inside .sunwell (prevent .sunwell/.sunwell nesting)
    if ".sunwell" in project_root.parts:
        raise ValueError(f"Cannot create .sunwell inside .sunwell: {project_root}")

    from sunwell.knowledge.project.state import resolve_state_dir

    # In-tree directory (manifest, config, gitignore)
    sunwell_dir = project_root / ".sunwell"
    sunwell_dir.mkdir(parents=True, exist_ok=True)

    # State directory (may be the same as sunwell_dir or external)
    state_dir = resolve_state_dir(project_root)

    # Create state directory structure
    state_subdirs = [
        state_dir / "team",
        state_dir / "intelligence",
        state_dir / "sessions",
    ]
    # In-tree subdirs (user-facing)
    in_tree_subdirs = [
        sunwell_dir / "personal",
        sunwell_dir / "project",
    ]

    for directory in state_subdirs + in_tree_subdirs:
        directory.mkdir(parents=True, exist_ok=True)

    # Create .gitignore in the in-tree directory
    create_sunwell_gitignore(sunwell_dir)

    return sunwell_dir
