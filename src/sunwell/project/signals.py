"""Project Signal Gathering (RFC-079).

Collect signals that indicate project type and state from filesystem.
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GitStatus:
    """Git repository status."""

    branch: str = "unknown"
    """Current branch name."""

    commit_count: int = 0
    """Total commit count."""

    uncommitted_changes: bool = False
    """Whether there are uncommitted changes."""

    recent_commits: tuple[str, ...] = ()
    """Recent commit messages (up to 5)."""


@dataclass
class ProjectSignals:
    """Signals collected from project filesystem.

    These signals are used to classify project type and state.
    """

    path: Path = field(default_factory=lambda: Path("."))
    """Project root path."""

    # Code signals
    has_package_json: bool = False
    has_pyproject: bool = False
    has_cargo: bool = False
    has_go_mod: bool = False
    has_makefile: bool = False
    has_src_dir: bool = False

    # Documentation signals
    has_docs_dir: bool = False
    has_sphinx_conf: bool = False
    has_mkdocs: bool = False
    markdown_count: int = 0

    # Data signals
    has_notebooks: bool = False
    has_data_dir: bool = False
    has_csv_files: bool = False

    # Planning signals
    has_backlog: bool = False
    has_roadmap: bool = False
    has_rfc_dir: bool = False

    # Creative signals
    has_prose: bool = False
    has_fountain: bool = False

    # State signals
    git_status: GitStatus | None = None
    readme_content: str | None = None
    recent_files: list[Path] = field(default_factory=list)

    @property
    def summary(self) -> tuple[str, ...]:
        """Return a tuple of signal names that are true."""
        signals = []
        if self.has_package_json:
            signals.append("has_package_json")
        if self.has_pyproject:
            signals.append("has_pyproject")
        if self.has_cargo:
            signals.append("has_cargo")
        if self.has_go_mod:
            signals.append("has_go_mod")
        if self.has_makefile:
            signals.append("has_makefile")
        if self.has_src_dir:
            signals.append("has_src_dir")
        if self.has_docs_dir:
            signals.append("has_docs_dir")
        if self.has_sphinx_conf:
            signals.append("has_sphinx_conf")
        if self.has_mkdocs:
            signals.append("has_mkdocs")
        if self.markdown_count > 5:
            signals.append(f"markdown_count_{self.markdown_count}")
        if self.has_notebooks:
            signals.append("has_notebooks")
        if self.has_data_dir:
            signals.append("has_data_dir")
        if self.has_csv_files:
            signals.append("has_csv_files")
        if self.has_backlog:
            signals.append("has_backlog")
        if self.has_roadmap:
            signals.append("has_roadmap")
        if self.has_rfc_dir:
            signals.append("has_rfc_dir")
        if self.has_prose:
            signals.append("has_prose")
        if self.has_fountain:
            signals.append("has_fountain")
        if self.git_status and self.git_status.commit_count > 0:
            signals.append("has_git_history")
        if self.readme_content:
            signals.append("has_readme")
        return tuple(signals)


def gather_project_signals(path: Path) -> ProjectSignals:
    """Collect signals that indicate project type and state.

    Args:
        path: Project root directory.

    Returns:
        ProjectSignals with all detected signals.
    """
    signals = ProjectSignals(path=path)

    # Code signals
    signals.has_package_json = (path / "package.json").exists()
    signals.has_pyproject = (path / "pyproject.toml").exists()
    signals.has_cargo = (path / "Cargo.toml").exists()
    signals.has_go_mod = (path / "go.mod").exists()
    signals.has_makefile = (path / "Makefile").exists()
    signals.has_src_dir = (path / "src").is_dir()

    # Documentation signals
    signals.has_docs_dir = (path / "docs").is_dir()
    signals.has_sphinx_conf = (path / "docs" / "conf.py").exists() or (
        path / "conf.py"
    ).exists()
    signals.has_mkdocs = (path / "mkdocs.yml").exists() or (path / "mkdocs.yaml").exists()
    signals.markdown_count = len(list(path.glob("**/*.md")))

    # Data signals
    signals.has_notebooks = len(list(path.glob("**/*.ipynb"))) > 0
    signals.has_data_dir = (path / "data").is_dir()
    signals.has_csv_files = len(list(path.glob("**/*.csv"))) > 0

    # Planning signals
    signals.has_backlog = (path / ".sunwell" / "backlog").exists() or (
        path / ".sunwell" / "goals"
    ).exists()
    signals.has_roadmap = any(path.glob("**/ROADMAP*")) or any(path.glob("**/roadmap*"))
    signals.has_rfc_dir = (
        (path / "docs" / "rfcs").is_dir()
        or (path / "rfcs").is_dir()
        or (path / "docs" / "rfc").is_dir()
    )

    # Creative signals
    signals.has_prose = (path / "manuscript").is_dir() or (path / "chapters").is_dir()
    signals.has_fountain = len(list(path.glob("**/*.fountain"))) > 0

    # State signals
    signals.git_status = _get_git_status(path)
    signals.readme_content = _read_readme(path)
    signals.recent_files = _get_recently_modified(path, limit=10)

    return signals


def _get_git_status(path: Path) -> GitStatus | None:
    """Get git repository status."""
    if not (path / ".git").exists():
        return None

    status = GitStatus()

    try:
        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            status = GitStatus(branch=result.stdout.strip())

        # Get commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            status = GitStatus(
                branch=status.branch,
                commit_count=int(result.stdout.strip()),
            )

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            status = GitStatus(
                branch=status.branch,
                commit_count=status.commit_count,
                uncommitted_changes=bool(result.stdout.strip()),
            )

        # Get recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-5", "--format=%s"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            commits = tuple(result.stdout.strip().split("\n")) if result.stdout.strip() else ()
            status = GitStatus(
                branch=status.branch,
                commit_count=status.commit_count,
                uncommitted_changes=status.uncommitted_changes,
                recent_commits=commits,
            )

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return status

    return status


def _read_readme(path: Path) -> str | None:
    """Read README content."""
    readme_names = ["README.md", "README.rst", "README.txt", "README", "readme.md"]

    for name in readme_names:
        readme_path = path / name
        if readme_path.exists():
            try:
                return readme_path.read_text(encoding="utf-8")[:2000]  # Limit to 2KB
            except (OSError, UnicodeDecodeError):
                continue

    return None


def _get_recently_modified(path: Path, limit: int = 10) -> list[Path]:
    """Get recently modified files."""
    try:
        # Get all files, sorted by modification time
        files = []
        for file_path in path.rglob("*"):
            if file_path.is_file() and not _should_ignore(file_path):
                try:
                    mtime = file_path.stat().st_mtime
                    files.append((mtime, file_path))
                except OSError:
                    continue

        # Sort by modification time (newest first) and return paths
        files.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in files[:limit]]

    except OSError:
        return []


def _should_ignore(path: Path) -> bool:
    """Check if path should be ignored."""
    ignore_patterns = {
        ".git",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".sunwell",
        "target",  # Rust
        ".cargo",
    }

    return any(part in ignore_patterns for part in path.parts)


def format_dir_tree(path: Path, max_depth: int = 2, prefix: str = "") -> str:
    """Format directory tree for LLM context."""
    lines = []

    try:
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        dirs = [p for p in items if p.is_dir() and not _should_ignore(p)]
        files = [p for p in items if p.is_file()][:10]  # Limit files

        for item in files:
            lines.append(f"{prefix}{item.name}")

        if max_depth > 0:
            for d in dirs[:5]:  # Limit directories
                lines.append(f"{prefix}{d.name}/")
                subtree = format_dir_tree(d, max_depth - 1, prefix + "  ")
                if subtree:
                    lines.append(subtree)

    except OSError:
        pass

    return "\n".join(lines)


def format_recent_commits(git_status: GitStatus | None, limit: int = 5) -> str:
    """Format recent commits for LLM context."""
    if not git_status or not git_status.recent_commits:
        return "No git history"

    commits = git_status.recent_commits[:limit]
    return "\n".join(f"- {commit}" for commit in commits)
