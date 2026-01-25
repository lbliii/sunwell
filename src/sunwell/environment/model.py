"""User Environment Model data structures (RFC-104).

The User Environment Model tracks:
- Project roots (where the user keeps projects)
- Project catalog (all known projects with metadata)
- Patterns (learned regularities across projects)
- Reference projects (gold standards for each category)

Composes with existing types:
- WorkspaceConfig from workspace/detector.py
- StateDag health scores from analysis/state_dag.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol, Self


class Serializable(Protocol):
    """Protocol for types that can be serialized to/from dict."""

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> Self: ...


@dataclass(frozen=True, slots=True)
class ProjectRoot:
    """A directory where the user keeps projects.

    Attributes:
        path: Absolute path to the root directory.
        discovered_at: When this root was first discovered.
        project_count: Number of projects found under this root.
        primary_type: Dominant project type ("python", "docs", "go", "mixed").
        scan_frequency: How often projects here change ("often", "sometimes", "rarely").
    """

    path: Path
    discovered_at: datetime
    project_count: int
    primary_type: str
    scan_frequency: str = "sometimes"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": str(self.path),
            "discovered_at": self.discovered_at.isoformat(),
            "project_count": self.project_count,
            "primary_type": self.primary_type,
            "scan_frequency": self.scan_frequency,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectRoot:
        """Deserialize from dictionary."""
        return cls(
            path=Path(data["path"]),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            project_count=data["project_count"],
            primary_type=data["primary_type"],
            scan_frequency=data.get("scan_frequency", "sometimes"),
        )


@dataclass(frozen=True, slots=True)
class ProjectEntry:
    """A known project in the user's environment.

    Lightweight wrapper around project metadata. Does NOT store full
    WorkspaceConfig to keep serialization simple. The project_type and
    markers are inferred from filesystem checks.

    Attributes:
        path: Absolute path to the project root.
        name: Project name (directory name).
        project_type: Inferred type ("python", "docs", "go", "node", "unknown").
        health_score: Cached from last StateDag scan (0.0-1.0), or None.
        last_scanned: When was the project last scanned.
        is_reference: User marked this as a gold standard.
        tags: User-defined tags for categorization.
        is_git: Whether this is a git repository.
    """

    path: Path
    name: str
    project_type: str
    health_score: float | None = None
    last_scanned: datetime | None = None
    is_reference: bool = False
    tags: tuple[str, ...] = ()
    is_git: bool = False

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": str(self.path),
            "name": self.name,
            "project_type": self.project_type,
            "health_score": self.health_score,
            "last_scanned": self.last_scanned.isoformat() if self.last_scanned else None,
            "is_reference": self.is_reference,
            "tags": list(self.tags),
            "is_git": self.is_git,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectEntry:
        """Deserialize from dictionary."""
        return cls(
            path=Path(data["path"]),
            name=data["name"],
            project_type=data["project_type"],
            health_score=data.get("health_score"),
            last_scanned=(
                datetime.fromisoformat(data["last_scanned"])
                if data.get("last_scanned")
                else None
            ),
            is_reference=data.get("is_reference", False),
            tags=tuple(data.get("tags", [])),
            is_git=data.get("is_git", False),
        )

    def with_health(self, score: float, scanned_at: datetime) -> ProjectEntry:
        """Return a new ProjectEntry with updated health info."""
        return ProjectEntry(
            path=self.path,
            name=self.name,
            project_type=self.project_type,
            health_score=score,
            last_scanned=scanned_at,
            is_reference=self.is_reference,
            tags=self.tags,
            is_git=self.is_git,
        )

    def with_reference(self, is_reference: bool) -> ProjectEntry:
        """Return a new ProjectEntry with updated reference status."""
        return ProjectEntry(
            path=self.path,
            name=self.name,
            project_type=self.project_type,
            health_score=self.health_score,
            last_scanned=self.last_scanned,
            is_reference=is_reference,
            tags=self.tags,
            is_git=self.is_git,
        )

    def with_tags(self, tags: tuple[str, ...]) -> ProjectEntry:
        """Return a new ProjectEntry with updated tags."""
        return ProjectEntry(
            path=self.path,
            name=self.name,
            project_type=self.project_type,
            health_score=self.health_score,
            last_scanned=self.last_scanned,
            is_reference=self.is_reference,
            tags=tags,
            is_git=self.is_git,
        )


@dataclass(frozen=True, slots=True)
class Pattern:
    """A learned pattern across projects.

    Patterns are extracted from project structures and configurations.
    They help Sunwell understand user conventions.

    Attributes:
        name: Pattern identifier (e.g., "pyproject_config", "src_layout").
        description: Human-readable description.
        frequency: How many projects exhibit this pattern.
        examples: Sample project paths that have this pattern.
        confidence: Pattern strength (frequency / applicable projects).
    """

    name: str
    description: str
    frequency: int
    examples: tuple[Path, ...]
    confidence: float

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency,
            "examples": [str(p) for p in self.examples[:5]],  # Limit examples
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Pattern:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            frequency=data["frequency"],
            examples=tuple(Path(p) for p in data.get("examples", [])),
            confidence=data["confidence"],
        )


@dataclass(slots=True)
class UserEnvironment:
    """The complete environment model.

    Stored at ~/.sunwell/environment.json. Contains all known projects,
    roots, patterns, and reference mappings.

    Attributes:
        roots: Directories where the user keeps projects.
        projects: All known projects with metadata.
        patterns: Learned patterns across projects.
        reference_projects: Category → path mapping for gold standards.
        version: Schema version for migration.
        updated_at: When the environment was last modified.
    """

    roots: list[ProjectRoot] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    reference_projects: dict[str, Path] = field(default_factory=dict)
    version: int = 1
    updated_at: datetime = field(default_factory=datetime.now)
    _project_index: dict[Path, ProjectEntry] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Build index from projects list for O(1) lookups."""
        if not self._project_index and self.projects:
            self._project_index = {p.path.resolve(): p for p in self.projects}

    def find_similar(self, project_path: Path) -> list[ProjectEntry]:
        """Find projects similar to the given one.

        Similarity is based on project_type. Returns projects of the
        same type, excluding the input project.

        Args:
            project_path: Path to the target project.

        Returns:
            List of similar ProjectEntry objects.
        """
        target = self.get_project(project_path)
        if not target:
            return []
        resolved = project_path.resolve()
        return [
            p
            for p in self.projects
            if p.project_type == target.project_type and p.path.resolve() != resolved
        ]

    def get_project(self, path: Path) -> ProjectEntry | None:
        """Get a project by path. O(1) lookup.

        Args:
            path: Path to the project (resolved to absolute).

        Returns:
            ProjectEntry if found, None otherwise.
        """
        return self._project_index.get(path.resolve())

    def get_reference_for(self, category: str) -> ProjectEntry | None:
        """Get the gold standard project for a category.

        Args:
            category: Project type/category (e.g., "docs", "python").

        Returns:
            ProjectEntry if a reference exists for the category.
        """
        ref_path = self.reference_projects.get(category)
        return self.get_project(ref_path) if ref_path else None

    def suggest_location(self, project_type: str) -> Path | None:
        """Suggest where to create a new project of this type.

        Returns the root directory that primarily contains projects
        of the given type. Falls back to the first root if no match.

        Args:
            project_type: Type of project ("python", "docs", etc.).

        Returns:
            Suggested root path, or None if no roots exist.
        """
        for root in self.roots:
            if root.primary_type == project_type:
                return root.path
        return self.roots[0].path if self.roots else None

    def add_project(self, entry: ProjectEntry) -> None:
        """Add or update a project in the catalog.

        If a project with the same path exists, it is replaced.

        Args:
            entry: ProjectEntry to add/update.
        """
        resolved = entry.path.resolve()
        old = self._project_index.get(resolved)
        if old:
            self.projects.remove(old)
        self.projects.append(entry)
        self._project_index[resolved] = entry
        self.updated_at = datetime.now()

    def remove_project(self, path: Path) -> bool:
        """Remove a project from the catalog.

        Args:
            path: Path to the project to remove.

        Returns:
            True if a project was removed, False if not found.
        """
        resolved = path.resolve()
        old = self._project_index.pop(resolved, None)
        if old:
            self.projects.remove(old)
            self.updated_at = datetime.now()
            return True
        return False

    def set_reference(self, category: str, path: Path) -> None:
        """Set a project as the reference for a category.

        Args:
            category: Category name (e.g., "docs", "python").
            path: Path to the project.
        """
        self.reference_projects[category] = path.resolve()
        # Mark the project as reference
        project = self.get_project(path)
        if project:
            self.add_project(project.with_reference(True))
        self.updated_at = datetime.now()

    def remove_reference(self, category: str) -> bool:
        """Remove a reference for a category.

        Args:
            category: Category to remove reference for.

        Returns:
            True if removed, False if category had no reference.
        """
        if category in self.reference_projects:
            path = self.reference_projects.pop(category)
            # Unmark the project if it's not a reference for any other category
            if path not in self.reference_projects.values():
                project = self.get_project(path)
                if project:
                    self.add_project(project.with_reference(False))
            self.updated_at = datetime.now()
            return True
        return False

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "roots": [r.to_dict() for r in self.roots],
            "projects": [p.to_dict() for p in self.projects],
            "patterns": [p.to_dict() for p in self.patterns],
            "references": {k: str(v) for k, v in self.reference_projects.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> UserEnvironment:
        """Deserialize from dictionary."""
        return cls(
            version=data.get("version", 1),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else datetime.now()
            ),
            roots=[ProjectRoot.from_dict(r) for r in data.get("roots", [])],
            projects=[ProjectEntry.from_dict(p) for p in data.get("projects", [])],
            patterns=[Pattern.from_dict(p) for p in data.get("patterns", [])],
            reference_projects={
                k: Path(v) for k, v in data.get("references", {}).items()
            },
        )
