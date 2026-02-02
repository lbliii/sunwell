"""Project structure awareness for task planning.

Provides utilities to help planners choose correct file locations
based on project conventions and existing structure.

This addresses the "wrong file location" problem where parallel tasks
might create files at incorrect paths without understanding project layout.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# Common project structure patterns
STRUCTURE_PATTERNS: dict[str, dict[str, str]] = {
    # Python projects
    "python": {
        "types": "src/{project}/types/{name}.py",
        "models": "src/{project}/models/{name}.py",
        "utils": "src/{project}/utils/{name}.py",
        "tests": "tests/{category}/test_{name}.py",
        "config": "src/{project}/config/{name}.py",
    },
    # TypeScript projects
    "typescript": {
        "types": "src/types/{name}.ts",
        "models": "src/models/{name}.ts",
        "utils": "src/utils/{name}.ts",
        "tests": "tests/{name}.test.ts",
        "components": "src/components/{name}.tsx",
        "config": "src/config/{name}.ts",
    },
    # Go projects
    "go": {
        "types": "internal/{package}/{name}.go",
        "models": "internal/models/{name}.go",
        "utils": "pkg/{name}/{name}.go",
        "tests": "internal/{package}/{name}_test.go",
        "config": "internal/config/{name}.go",
    },
}

# File type to directory mapping
FILE_TYPE_DIRS: dict[str, list[str]] = {
    "type": ["types", "models", "interfaces", "schemas"],
    "util": ["utils", "helpers", "lib", "common"],
    "config": ["config", "settings", "configuration"],
    "test": ["tests", "test", "__tests__", "spec"],
    "component": ["components", "ui", "views"],
    "service": ["services", "api", "handlers"],
}


@dataclass(frozen=True, slots=True)
class PathSuggestion:
    """A suggested file path with confidence and reasoning."""

    path: str
    """Suggested file path (relative to workspace root)."""

    confidence: float
    """Confidence in this suggestion (0.0-1.0)."""

    reason: str
    """Why this path was suggested."""


@dataclass(slots=True)
class ProjectStructure:
    """Analyzes and suggests paths based on project conventions.

    Examines existing project structure to infer where new files
    should be placed, helping prevent the "wrong location" problem.

    Usage:
        structure = ProjectStructure(workspace_path)
        await structure.analyze()

        suggestions = structure.suggest_path(
            name="todo",
            file_type="type",
            description="Todo type definitions",
        )
        # Returns: [PathSuggestion("src/types/todo.ts", 0.9, "existing types dir")]
    """

    workspace: Path
    """Workspace root path."""

    project_type: str | None = None
    """Detected project type (python, typescript, go, etc.)."""

    src_root: str | None = None
    """Detected source root (src/, lib/, internal/, etc.)."""

    existing_dirs: set[str] = field(default_factory=set)
    """Set of existing directories (relative paths)."""

    conventions: dict[str, str] = field(default_factory=dict)
    """Detected conventions: file_type -> directory pattern."""

    def __post_init__(self) -> None:
        """Initialize with empty state."""
        self.existing_dirs = set()
        self.conventions = {}

    async def analyze(self) -> None:
        """Analyze project structure to detect conventions.

        This is a synchronous operation that scans the filesystem.
        Should be called once at the start of planning.
        """
        self._detect_project_type()
        self._scan_directories()
        self._detect_conventions()

    def _detect_project_type(self) -> None:
        """Detect the project type from config files."""
        if (self.workspace / "pyproject.toml").exists():
            self.project_type = "python"
        elif (self.workspace / "setup.py").exists():
            self.project_type = "python"
        elif (self.workspace / "package.json").exists():
            # Check for TypeScript
            if (self.workspace / "tsconfig.json").exists():
                self.project_type = "typescript"
            else:
                self.project_type = "javascript"
        elif (self.workspace / "go.mod").exists():
            self.project_type = "go"
        elif (self.workspace / "Cargo.toml").exists():
            self.project_type = "rust"

    def _scan_directories(self, max_depth: int = 4) -> None:
        """Scan directories up to max_depth."""
        for path in self.workspace.rglob("*"):
            if path.is_dir():
                rel_path = path.relative_to(self.workspace)
                # Skip common non-source directories
                parts = rel_path.parts
                if any(p.startswith(".") or p == "__pycache__" or p == "node_modules"
                       for p in parts):
                    continue
                if len(parts) <= max_depth:
                    self.existing_dirs.add(str(rel_path))

    def _detect_conventions(self) -> None:
        """Detect conventions from existing directory structure."""
        # Detect source root
        for candidate in ["src", "lib", "internal", "pkg", "app"]:
            if candidate in self.existing_dirs:
                self.src_root = candidate
                break

        # Detect type/model locations
        for file_type, dir_names in FILE_TYPE_DIRS.items():
            for dir_name in dir_names:
                # Check direct match
                if dir_name in self.existing_dirs:
                    self.conventions[file_type] = dir_name
                    break
                # Check under src root
                if self.src_root and f"{self.src_root}/{dir_name}" in self.existing_dirs:
                    self.conventions[file_type] = f"{self.src_root}/{dir_name}"
                    break

    def suggest_path(
        self,
        name: str,
        file_type: str = "file",
        description: str | None = None,
        category: str | None = None,
    ) -> list[PathSuggestion]:
        """Suggest appropriate paths for a new file.

        Args:
            name: Name of the file/module (without extension)
            file_type: Type of file (type, util, config, test, component, etc.)
            description: Optional description to help infer placement
            category: Optional category (e.g., "unit", "integration" for tests)

        Returns:
            List of PathSuggestion, sorted by confidence (highest first)
        """
        suggestions: list[PathSuggestion] = []
        ext = self._get_extension()
        name = self._normalize_name(name)

        # 1. Check if we have a convention for this file type
        if file_type in self.conventions:
            base_dir = self.conventions[file_type]
            path = f"{base_dir}/{name}{ext}"
            suggestions.append(PathSuggestion(
                path=path,
                confidence=0.9,
                reason=f"Existing {file_type} directory at {base_dir}",
            ))

        # 2. Check project-type-specific patterns
        if self.project_type and self.project_type in STRUCTURE_PATTERNS:
            patterns = STRUCTURE_PATTERNS[self.project_type]
            if file_type in patterns:
                pattern = patterns[file_type]
                # Fill in template variables
                path = pattern.format(
                    project=self._detect_project_name(),
                    name=name,
                    category=category or "unit",
                    package=name,
                )
                suggestions.append(PathSuggestion(
                    path=path,
                    confidence=0.7,
                    reason=f"Standard {self.project_type} convention",
                ))

        # 3. Infer from description if available
        if description:
            inferred_type = self._infer_type_from_description(description)
            if inferred_type and inferred_type in self.conventions:
                base_dir = self.conventions[inferred_type]
                path = f"{base_dir}/{name}{ext}"
                if not any(s.path == path for s in suggestions):
                    suggestions.append(PathSuggestion(
                        path=path,
                        confidence=0.6,
                        reason=f"Inferred {inferred_type} from description",
                    ))

        # 4. Fallback: use src root or top-level
        if not suggestions:
            if self.src_root:
                path = f"{self.src_root}/{name}{ext}"
            else:
                path = f"{name}{ext}"
            suggestions.append(PathSuggestion(
                path=path,
                confidence=0.4,
                reason="Fallback to source root",
            ))

        # Sort by confidence (highest first)
        return sorted(suggestions, key=lambda s: -s.confidence)

    def _get_extension(self) -> str:
        """Get file extension based on project type."""
        extensions = {
            "python": ".py",
            "typescript": ".ts",
            "javascript": ".js",
            "go": ".go",
            "rust": ".rs",
        }
        return extensions.get(self.project_type or "", ".py")

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for use in file paths."""
        # Remove common prefixes/suffixes
        name = re.sub(r"(Type|Interface|Model|Schema)$", "", name, flags=re.IGNORECASE)
        # Convert to snake_case for Python, keep as-is for others
        if self.project_type == "python":
            name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name).lower()
        return name

    def _detect_project_name(self) -> str:
        """Detect the project/package name."""
        # Try to get from pyproject.toml, package.json, etc.
        if self.project_type == "python":
            # Check for src/{name} pattern
            if self.src_root == "src":
                src_path = self.workspace / "src"
                if src_path.exists():
                    for child in src_path.iterdir():
                        if child.is_dir() and not child.name.startswith(("_", ".")):
                            return child.name
        return self.workspace.name

    def _infer_type_from_description(self, description: str) -> str | None:
        """Infer file type from description keywords."""
        desc_lower = description.lower()

        keywords = {
            "type": ["type", "interface", "protocol", "schema", "model", "dataclass"],
            "util": ["utility", "helper", "common", "shared"],
            "config": ["config", "settings", "configuration", "options"],
            "test": ["test", "spec", "fixture"],
            "component": ["component", "view", "page", "widget", "ui"],
            "service": ["service", "api", "handler", "controller"],
        }

        for file_type, kws in keywords.items():
            if any(kw in desc_lower for kw in kws):
                return file_type

        return None

    def validate_path(self, path: str) -> tuple[bool, str | None]:
        """Validate that a proposed path follows conventions.

        Args:
            path: Proposed file path (relative to workspace)

        Returns:
            Tuple of (is_valid, warning_message_if_not)
        """
        path_parts = Path(path).parts

        # Check for root-level files (often wrong)
        if len(path_parts) == 1 and self.src_root:
            return False, f"File at root level - should be under {self.src_root}/"

        # Check for common misplacements
        if path_parts[0] not in (self.src_root or "", "tests", "test", "docs"):
            if path_parts[0] not in self.existing_dirs:
                return False, f"Creating new top-level directory '{path_parts[0]}'"

        return True, None


def infer_target_path(
    task_id: str,
    task_description: str,
    produces: frozenset[str],
    structure: ProjectStructure | None = None,
    workspace: Path | None = None,
) -> str | None:
    """Infer an appropriate target_path for a task.

    Convenience function for use in task planning.

    Args:
        task_id: Task identifier
        task_description: Description of what the task does
        produces: Set of artifacts the task produces
        structure: Optional pre-analyzed project structure
        workspace: Optional workspace path (required if structure not provided)

    Returns:
        Suggested target path, or None if cannot determine
    """
    # Get or create structure analyzer
    if structure is None:
        if workspace is None:
            return None
        structure = ProjectStructure(workspace=workspace)
        # Note: Synchronous scan - in production use async analyze()
        structure._detect_project_type()
        structure._scan_directories()
        structure._detect_conventions()

    # Extract likely name from task ID or produces
    name = task_id.replace("-", "_").replace("task_", "")
    if produces:
        # Use first produced artifact as name hint
        name = list(produces)[0].replace(".py", "").replace(".ts", "")

    # Infer file type from description
    file_type = structure._infer_type_from_description(task_description) or "file"

    suggestions = structure.suggest_path(
        name=name,
        file_type=file_type,
        description=task_description,
    )

    if suggestions:
        return suggestions[0].path

    return None
