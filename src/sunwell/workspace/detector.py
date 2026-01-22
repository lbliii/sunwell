"""Workspace and repository detection (RFC-024 extended).

Extended for RFC-024 with:
- .sunwell/config.yaml support
- Trust level suggestions (not auto-applied)
- Monorepo subproject detection
"""


import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Workspace Configuration (RFC-024)
# =============================================================================

@dataclass(frozen=True, slots=True)
class Workspace:
    """Detected workspace information (legacy compatibility)."""

    root: Path
    """Root directory of the workspace."""

    is_git: bool
    """Whether this is a git repository."""

    name: str
    """Name of the workspace (directory name)."""

    ignore_patterns: tuple[str, ...]
    """Patterns to ignore when scanning files."""


@dataclass(frozen=True)
class WorkspaceConfig:
    """Extended workspace configuration with trust suggestions (RFC-024).

    This extends the basic Workspace with:
    - Trust level suggestions based on detection
    - .sunwell/config.yaml support
    - Monorepo subproject detection

    Security note: Trust levels are SUGGESTED, not automatically applied.
    Users must explicitly opt in via --trust or .sunwell/config.yaml.
    """

    root: Path
    """Root directory of the workspace."""

    is_git: bool
    """Whether this is a git repository."""

    name: str
    """Name of the workspace (directory name)."""

    ignore_patterns: tuple[str, ...] = ()
    """Patterns to ignore when scanning files."""

    # New fields for RFC-024
    suggested_trust: str = "workspace"
    """Suggested trust level based on detection. NOT automatically applied.

    Values: discovery, read_only, workspace, shell, full
    """

    has_sunwell_config: bool = False
    """Whether .sunwell/config.yaml exists."""

    config_trust: str | None = None
    """Trust level from .sunwell/config.yaml if present."""

    subprojects: tuple[Path, ...] = ()
    """Detected subproject roots in monorepo."""

    current_subproject: Path | None = None
    """Which subproject cwd is in (if any)."""

    def to_workspace(self) -> Workspace:
        """Convert to legacy Workspace for compatibility."""
        return Workspace(
            root=self.root,
            is_git=self.is_git,
            name=self.name,
            ignore_patterns=self.ignore_patterns,
        )


# =============================================================================
# Workspace Detector (RFC-024 Extended)
# =============================================================================

class WorkspaceDetector:
    """Detects workspace root and configuration.

    Extended for RFC-024 with:
    - .sunwell/config.yaml support
    - Trust level suggestions (not auto-applied)
    - Monorepo subproject detection

    Detection order:
    1. Check for .sunwell/config.yaml (explicit configuration)
    2. Check for git repository root
    3. Check for project markers (pyproject.toml, package.json, etc.)
    4. Fall back to current directory
    """

    DEFAULT_IGNORE = (
        ".git", ".venv", "venv", "__pycache__", "node_modules",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc", "*.pyo",
        ".DS_Store", "*.egg-info", "dist", "build", ".tox", ".coverage", "htmlcov",
    )

    PROJECT_MARKERS = (
        "pyproject.toml", "setup.py", "setup.cfg",  # Python
        "package.json", "package-lock.json",         # Node.js
        "Cargo.toml", "Cargo.lock",                  # Rust
        "go.mod", "go.sum",                          # Go
        "pom.xml", "build.gradle", "build.gradle.kts",  # JVM
        "Makefile", "CMakeLists.txt",                # C/C++
        "Gemfile", "*.gemspec",                      # Ruby
        "composer.json",                             # PHP
    )

    def detect(self, start_path: Path | None = None) -> Workspace:
        """Detect workspace from starting path (legacy interface).

        Args:
            start_path: Path to start detection from. Defaults to cwd.

        Returns:
            Detected workspace information.
        """
        config = self.detect_config(start_path)
        return config.to_workspace()

    def detect_config(self, start_path: Path | None = None) -> WorkspaceConfig:
        """Detect workspace with full RFC-024 configuration.

        Detection order:
        1. Check for .sunwell/config.yaml (explicit configuration)
        2. Check for git repository root
        3. Check for project markers (pyproject.toml, package.json, etc.)
        4. Fall back to current directory

        Security note: Trust levels are SUGGESTED, not automatically applied.
        Users must explicitly opt in via --trust or .sunwell/config.yaml.

        Args:
            start_path: Path to start detection from. Defaults to cwd.

        Returns:
            WorkspaceConfig with detected settings and suggestions.
        """
        start = Path(start_path) if start_path else Path.cwd()
        start = start.resolve()

        # 1. Look for .sunwell/ config (explicit user configuration)
        config_root = self._find_sunwell_config(start)
        if config_root:
            return self._load_sunwell_config(config_root, start)

        # 2. Look for git root
        git_root = self._find_git_root(start)
        if git_root:
            subprojects = self._detect_subprojects(git_root)
            current_sub = self._find_current_subproject(start, subprojects)

            return WorkspaceConfig(
                root=git_root,
                is_git=True,
                name=git_root.name,
                ignore_patterns=self._load_gitignore(git_root),
                # SUGGEST read_only for git repos - safe default
                # Users can opt into workspace/shell via --trust
                suggested_trust="read_only",
                subprojects=tuple(subprojects),
                current_subproject=current_sub,
            )

        # 3. Look for project markers
        project_root = self._find_project_root(start)
        if project_root:
            return WorkspaceConfig(
                root=project_root,
                is_git=False,
                name=project_root.name,
                ignore_patterns=self.DEFAULT_IGNORE,
                suggested_trust="read_only",
            )

        # 4. Fall back to cwd - most conservative
        return WorkspaceConfig(
            root=start if start.is_dir() else start.parent,
            is_git=False,
            name=start.name,
            ignore_patterns=self.DEFAULT_IGNORE,
            suggested_trust="discovery",  # Unknown location = very conservative
        )

    def _find_sunwell_config(self, start: Path) -> Path | None:
        """Walk up looking for .sunwell/ directory."""
        current = start
        while current != current.parent:
            if (current / ".sunwell").is_dir():
                return current
            current = current.parent
        return None

    def _load_sunwell_config(self, root: Path, cwd: Path) -> WorkspaceConfig:
        """Load configuration from .sunwell/config.yaml."""
        config_path = root / ".sunwell" / "config.yaml"
        config: dict = {}

        if config_path.exists():
            try:
                import yaml
                with open(config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            except ImportError:
                # yaml not available, use basic parsing
                pass
            except Exception:
                # Invalid config, use defaults
                pass

        # Parse trust level from config
        config_trust = config.get("trust_level")
        if config_trust and config_trust not in ("discovery", "read_only", "workspace", "shell", "full"):
            config_trust = None  # Invalid trust level

        # Check for git
        is_git = (root / ".git").exists()

        # Get ignore patterns
        ignore_patterns = tuple(config.get("ignore", self.DEFAULT_IGNORE))

        # Detect subprojects if git repo
        subprojects: list[Path] = []
        current_sub = None
        if is_git:
            subprojects = self._detect_subprojects(root)
            current_sub = self._find_current_subproject(cwd, subprojects)

        return WorkspaceConfig(
            root=root,
            is_git=is_git,
            name=root.name,
            ignore_patterns=ignore_patterns,
            has_sunwell_config=True,
            config_trust=config_trust,
            # If config specifies trust, suggest that; otherwise suggest workspace
            suggested_trust=config_trust or "workspace",
            subprojects=tuple(subprojects),
            current_subproject=current_sub,
        )

    def _find_git_root(self, path: Path) -> Path | None:
        """Find git repository root."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _find_project_root(self, start: Path) -> Path | None:
        """Walk up looking for project markers."""
        current = start
        while current != current.parent:
            for marker in self.PROJECT_MARKERS:
                if "*" in marker:
                    # Glob pattern
                    if list(current.glob(marker)):
                        return current
                elif (current / marker).exists():
                    return current
            current = current.parent
        return None

    def _detect_subprojects(self, root: Path) -> list[Path]:
        """Find project roots within a monorepo."""
        subprojects: set[Path] = set()

        # Skip these directories entirely
        skip_dirs = {".git", "node_modules", "vendor", ".venv", "venv",
                     "__pycache__", "dist", "build", ".tox"}

        for marker in self.PROJECT_MARKERS:
            if "*" in marker:
                continue  # Skip glob patterns for performance

            try:
                for match in root.rglob(marker):
                    # Check if any parent is in skip list
                    if any(skip in match.parts for skip in skip_dirs):
                        continue

                    # Don't include the root itself
                    if match.parent != root:
                        subprojects.add(match.parent)
            except PermissionError:
                continue  # Skip inaccessible directories

        return sorted(subprojects)

    def _find_current_subproject(
        self, cwd: Path, subprojects: list[Path]
    ) -> Path | None:
        """Find which subproject cwd is inside."""
        cwd = cwd.resolve()
        for sub in sorted(subprojects, key=lambda p: len(p.parts), reverse=True):
            try:
                cwd.relative_to(sub)
                return sub
            except ValueError:
                continue
        return None

    def _load_gitignore(self, root: Path) -> tuple[str, ...]:
        """Load ignore patterns from .gitignore."""
        patterns = list(self.DEFAULT_IGNORE)
        gitignore = root / ".gitignore"
        if gitignore.exists():
            try:
                with open(gitignore, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception:
                pass
        return tuple(patterns)


# =============================================================================
# Trust Level Resolution (RFC-024)
# =============================================================================

# Default trust level - WORKSPACE is a good balance
DEFAULT_TRUST = "workspace"


def resolve_trust_level(
    explicit_trust: str | None,
    config: WorkspaceConfig,
) -> str:
    """Resolve trust level with explicit > config > default precedence.

    Security: We NEVER auto-escalate based on detection alone.

    Args:
        explicit_trust: Trust level from --trust CLI flag
        config: Detected workspace configuration

    Returns:
        Resolved trust level string
    """
    # 1. Explicit flag takes precedence
    if explicit_trust:
        return explicit_trust.lower()

    # 2. Config file trust (user explicitly configured)
    if config.config_trust:
        return config.config_trust

    # 3. Default
    return DEFAULT_TRUST
