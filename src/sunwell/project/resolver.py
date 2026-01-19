"""Schema to Task resolver for RFC-035/RFC-034 integration.

This module provides the SchemaResolver that converts user-defined artifacts
into RFC-034 Tasks with proper dependency tracking, parallel grouping, and
contract awareness.

Example:
    ```python
    schema = ProjectSchema.load(project_root)
    resolver = SchemaResolver(schema)

    # Convert an artifact to a task
    task = resolver.resolve_artifact(artifact_path)

    # Or convert all artifacts in a directory
    tasks = resolver.resolve_all_artifacts(project_root / "artifacts")
    ```
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sunwell.naaru.types import Task, TaskMode
from sunwell.project.schema import ProjectSchema


@dataclass
class SchemaResolver:
    """Converts user artifact definitions into RFC-034 Tasks.

    The resolver is the bridge between domain-specific schemas and
    Sunwell's execution infrastructure. It handles:

    1. Template expansion: "Character_{id}" → "Character_john"
    2. Dependency resolution: requires/produces tracking
    3. Phase mapping: artifact_type → parallel_group
    4. Conflict detection: modifies set population
    """

    schema: ProjectSchema

    def resolve_artifact(self, artifact_path: Path) -> Task:
        """Convert a user's artifact definition into an RFC-034 Task.

        Args:
            artifact_path: Path to the artifact YAML file

        Returns:
            Task ready for execution

        Raises:
            ValueError: If artifact is invalid or type not in schema
        """
        with open(artifact_path) as f:
            artifact = yaml.safe_load(f)

        # Get artifact type
        type_name = artifact.get("type")
        if not type_name:
            raise ValueError(f"Artifact missing 'type' field: {artifact_path}")

        artifact_type = self.schema.get_artifact_type(type_name)
        if not artifact_type:
            raise ValueError(
                f"Unknown artifact type '{type_name}' in {artifact_path}. "
                f"Available types: {list(self.schema.artifact_types.keys())}"
            )

        # Get artifact ID
        artifact_id = artifact.get("id")
        if not artifact_id:
            raise ValueError(f"Artifact missing 'id' field: {artifact_path}")

        # Validate required fields
        missing_fields = []
        for field_name in artifact_type.fields.required:
            if field_name not in artifact:
                missing_fields.append(field_name)

        if missing_fields:
            raise ValueError(
                f"Artifact {artifact_id} missing required fields: {missing_fields}"
            )

        # Expand patterns
        produces = self._expand_pattern(artifact_type.produces_pattern, artifact)
        requires = self._expand_patterns(artifact_type.requires_patterns, artifact)
        modifies = self._expand_patterns(artifact_type.modifies_patterns, artifact)

        # Add conditional requirements
        for cond_req in artifact_type.conditional_requirements:
            if self._check_condition(cond_req.condition, artifact):
                if cond_req.iterate_over:
                    # Expand for each item in the collection
                    collection = artifact.get(cond_req.iterate_over, [])
                    for item in collection:
                        expanded = self._expand_pattern_simple(
                            cond_req.requires_pattern,
                            item,
                        )
                        requires = requires | frozenset([expanded])
                else:
                    expanded = self._expand_pattern(cond_req.requires_pattern, artifact)
                    requires = requires | expanded

        # Get phase mapping
        phase = self.schema.get_phase_for_artifact_type(type_name)
        parallel_group = phase.maps_to if phase else None

        # Default modifies to artifact file if not specified
        if not modifies:
            modifies = frozenset([str(artifact_path)])

        # Determine description
        name = artifact.get("name", artifact_id)
        description = f"Create {artifact_type.description}: {name}"

        return Task(
            id=artifact_id,
            description=description,
            mode=TaskMode.GENERATE,
            target_path=str(artifact_path),
            produces=produces,
            requires=requires,
            modifies=modifies,
            parallel_group=parallel_group,
            is_contract=artifact_type.is_contract,
            details={"artifact_type": type_name, "artifact_data": artifact},
        )

    def resolve_all_artifacts(
        self,
        artifacts_dir: Path,
        recursive: bool = True,
    ) -> list[Task]:
        """Convert all artifact files in a directory to Tasks.

        Args:
            artifacts_dir: Directory containing artifact YAML files
            recursive: Whether to search subdirectories

        Returns:
            List of Tasks for all valid artifacts
        """
        tasks: list[Task] = []

        # Find all YAML files
        pattern = "**/*.yaml" if recursive else "*.yaml"
        for artifact_path in artifacts_dir.glob(pattern):
            try:
                task = self.resolve_artifact(artifact_path)
                tasks.append(task)
            except (ValueError, yaml.YAMLError) as e:
                # Log warning but continue with other artifacts
                import warnings

                warnings.warn(
                    f"Skipping invalid artifact {artifact_path}: {e}",
                    stacklevel=2,
                )

        return tasks

    def build_task_graph(
        self,
        tasks: list[Task],
    ) -> list[Task]:
        """Add dependency links between tasks based on produces/requires.

        This post-processes tasks to set `depends_on` based on artifact
        dependencies (requires → produces).

        Args:
            tasks: List of tasks from resolve_all_artifacts

        Returns:
            Tasks with depends_on populated
        """
        # Build producer map: artifact → task_id
        producers: dict[str, str] = {}
        for task in tasks:
            for artifact in task.produces:
                producers[artifact] = task.id

        # Add dependencies
        updated_tasks = []
        for task in tasks:
            deps = list(task.depends_on)

            for required_artifact in task.requires:
                producer_id = producers.get(required_artifact)
                if producer_id and producer_id not in deps:
                    deps.append(producer_id)

            # Create updated task with new dependencies
            updated_task = Task(
                id=task.id,
                description=task.description,
                mode=task.mode,
                tools=task.tools,
                target_path=task.target_path,
                working_directory=task.working_directory,
                depends_on=tuple(deps),
                subtasks=task.subtasks,
                produces=task.produces,
                requires=task.requires,
                modifies=task.modifies,
                parallel_group=task.parallel_group,
                is_contract=task.is_contract,
                contract=task.contract,
                category=task.category,
                priority=task.priority,
                estimated_effort=task.estimated_effort,
                risk_level=task.risk_level,
                details=task.details,
                status=task.status,
                verification=task.verification,
                verification_command=task.verification_command,
            )
            updated_tasks.append(updated_task)

        return updated_tasks

    def _expand_pattern(
        self,
        pattern: str,
        artifact: dict[str, Any],
    ) -> frozenset[str]:
        """Expand a template pattern like 'Character_{id}' → 'Character_john'.

        Args:
            pattern: Template with {field} placeholders
            artifact: Artifact data for substitution

        Returns:
            Frozenset with the expanded pattern
        """
        result = self._expand_pattern_simple(pattern, artifact)
        return frozenset([result]) if result else frozenset()

    def _expand_pattern_simple(
        self,
        pattern: str,
        context: Any,
    ) -> str:
        """Expand a pattern with simple substitution.

        Args:
            pattern: Template with {field} placeholders
            context: Dict or string for substitution

        Returns:
            Expanded string
        """
        import re

        if isinstance(context, str):
            # Simple case: replace all {var} with the string
            return re.sub(r"\{[^}]+\}", context, pattern)

        if isinstance(context, dict):
            # Replace {field} with context[field]
            result = pattern
            for match in re.finditer(r"\{(\w+)\}", pattern):
                field_name = match.group(1)
                value = context.get(field_name, "")
                result = result.replace(match.group(0), str(value))
            return result

        return pattern

    def _expand_patterns(
        self,
        patterns: tuple[str, ...],
        artifact: dict[str, Any],
    ) -> frozenset[str]:
        """Expand multiple patterns.

        Args:
            patterns: Tuple of template patterns
            artifact: Artifact data for substitution

        Returns:
            Frozenset of all expanded patterns
        """
        results = set()
        for pattern in patterns:
            expanded = self._expand_pattern_simple(pattern, artifact)
            if expanded:
                results.add(expanded)
        return frozenset(results)

    def _check_condition(
        self,
        condition: str,
        artifact: dict[str, Any],
    ) -> bool:
        """Check if a condition is satisfied.

        Simple implementation: checks if the named field is truthy.

        Args:
            condition: Field name or simple condition
            artifact: Artifact data

        Returns:
            True if condition is satisfied
        """
        # Simple case: field name
        if condition in artifact:
            value = artifact[condition]
            # Truthy check
            if isinstance(value, (list, tuple)):
                return len(value) > 0
            return bool(value)
        return False


@dataclass
class ArtifactLoader:
    """Loads artifacts from a project directory.

    Provides utilities for discovering and loading artifact files,
    organizing them by type for validation.
    """

    schema: ProjectSchema

    def load_all_artifacts(
        self,
        project_root: Path | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Load all artifacts from the project, organized by type.

        Args:
            project_root: Root of the project (defaults to schema's root)

        Returns:
            Dict mapping artifact type → list of artifacts
        """
        root = project_root or self.schema.project_root
        if not root:
            raise ValueError("No project root specified")

        artifacts: dict[str, list[dict[str, Any]]] = {}

        # Initialize empty lists for all known types
        for type_name in self.schema.artifact_types:
            artifacts[type_name] = []

        # Search common locations
        artifacts_dir = root / "artifacts"
        if artifacts_dir.exists():
            self._load_from_directory(artifacts_dir, artifacts)

        # Also check for type-specific directories
        for type_name in self.schema.artifact_types:
            type_dir = root / type_name
            if type_dir.exists():
                self._load_from_directory(type_dir, artifacts)

            # Check plural form
            plural_dir = root / f"{type_name}s"
            if plural_dir.exists():
                self._load_from_directory(plural_dir, artifacts)

        return artifacts

    def _load_from_directory(
        self,
        directory: Path,
        artifacts: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Load artifacts from a directory into the artifacts dict."""
        for path in directory.glob("**/*.yaml"):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)

                if not data or not isinstance(data, dict):
                    continue

                type_name = data.get("type")
                if type_name and type_name in artifacts:
                    artifacts[type_name].append(data)
            except (yaml.YAMLError, OSError):
                # Skip invalid files
                continue
