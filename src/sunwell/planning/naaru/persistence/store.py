"""PlanStore - Thread-safe storage for SavedExecution objects."""

import json
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sunwell.planning.naaru.persistence.hashing import hash_goal
from sunwell.planning.naaru.persistence.plan_version import PlanDiff, PlanVersion
from sunwell.planning.naaru.persistence.saved_execution import SavedExecution

DEFAULT_PLANS_DIR = Path(".sunwell/plans")


@dataclass(slots=True)
class PlanStore:
    """Manages plan persistence with file locking.

    Thread-safe storage for SavedExecution objects.

    Attributes:
        base_path: Directory for plan files
        _lock: Thread lock for concurrent access

    Example:
        >>> store = PlanStore()
        >>> execution = SavedExecution(goal="Build API", graph=graph)
        >>> path = store.save(execution)
        >>>
        >>> # Load by goal hash
        >>> loaded = store.load(execution.goal_hash)
        >>>
        >>> # Or find by goal text
        >>> found = store.find_by_goal("Build API")
    """

    base_path: Path = field(default_factory=lambda: DEFAULT_PLANS_DIR)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        """Ensure storage directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, execution: SavedExecution) -> Path:
        """Save execution state to disk (thread-safe).

        Args:
            execution: The execution state to save

        Returns:
            Path to saved file
        """
        path = self.base_path / f"{execution.goal_hash}.json"

        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file, then atomic rename
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(execution.to_dict(), f, indent=2)
            temp_path.rename(path)

        return path

    def load(self, goal_hash: str) -> SavedExecution | None:
        """Load execution state from disk.

        Args:
            goal_hash: The goal hash to load

        Returns:
            SavedExecution if found, None otherwise
        """
        path = self.base_path / f"{goal_hash}.json"
        if not path.exists():
            return None

        with open(path) as f:
            return SavedExecution.from_dict(json.load(f))

    def find_by_goal(self, goal: str) -> SavedExecution | None:
        """Find execution by goal text (computes hash).

        Args:
            goal: The goal text

        Returns:
            SavedExecution if found, None otherwise
        """
        goal_hash = hash_goal(goal)
        return self.load(goal_hash)

    def exists(self, goal_hash: str) -> bool:
        """Check if a plan exists.

        Args:
            goal_hash: The goal hash to check

        Returns:
            True if plan exists
        """
        path = self.base_path / f"{goal_hash}.json"
        return path.exists()

    def delete(self, goal_hash: str) -> bool:
        """Delete a saved plan and its version history.

        Args:
            goal_hash: The goal hash to delete

        Returns:
            True if deleted, False if not found
        """
        path = self.base_path / f"{goal_hash}.json"
        trace_path = path.with_suffix(".trace.jsonl")
        version_dir = self.base_path / goal_hash

        deleted = False
        with self._lock:
            if path.exists():
                path.unlink()
                deleted = True
            if trace_path.exists():
                trace_path.unlink()
            # Also delete version history directory
            if version_dir.exists() and version_dir.is_dir():
                shutil.rmtree(version_dir)
                deleted = True

        return deleted

    def list_recent(self, limit: int = 10) -> list[SavedExecution]:
        """List recent executions.

        Args:
            limit: Maximum number to return

        Returns:
            List of SavedExecution objects, most recent first
        """
        if not self.base_path.exists():
            return []

        plans = sorted(
            self.base_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        results = []
        for p in plans[:limit]:
            if p.suffix == ".json" and not p.name.endswith(".trace.jsonl"):
                execution = self.load(p.stem)
                if execution:
                    results.append(execution)

        return results

    def list_all(self) -> list[tuple[str, Path]]:
        """List all saved plans.

        Returns:
            List of (goal_hash, path) tuples
        """
        if not self.base_path.exists():
            return []

        return [
            (p.stem, p)
            for p in self.base_path.glob("*.json")
            if not p.name.endswith(".trace.jsonl")
        ]

    def get_plan_age_hours(self, goal_hash: str) -> float | None:
        """Get age of a plan in hours.

        Args:
            goal_hash: The goal hash

        Returns:
            Age in hours, or None if not found
        """
        path = self.base_path / f"{goal_hash}.json"
        if not path.exists():
            return None

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return (datetime.now() - mtime).total_seconds() / 3600

    def clean_old(self, max_age_hours: float = 168.0, max_versions: int = 50) -> int:
        """Clean plans older than max_age_hours and prune old versions.

        Args:
            max_age_hours: Maximum age (default: 1 week)
            max_versions: Keep at most N versions per plan (default: 50)

        Returns:
            Number of items deleted (plans + versions)
        """
        deleted = 0

        # Age-based cleanup of main plan files
        for goal_hash, _path in self.list_all():
            age = self.get_plan_age_hours(goal_hash)
            if age and age > max_age_hours and self.delete(goal_hash):
                deleted += 1

        # Version cleanup
        for plan_dir in self.base_path.iterdir():
            if plan_dir.is_dir():
                versions = sorted(plan_dir.glob("v*.json"))
                if len(versions) > max_versions:
                    for old_version in versions[:-max_versions]:
                        old_version.unlink()
                        deleted += 1

        return deleted

    # =========================================================================
    # Plan Versioning (RFC-120)
    # =========================================================================

    def save_version(self, execution: SavedExecution, reason: str) -> PlanVersion:
        """Save a new version of a plan.

        Args:
            execution: The execution state to version
            reason: Why this version exists (e.g., "Initial plan", "User edit")

        Returns:
            The created PlanVersion
        """
        plan_id = execution.goal_hash
        versions = self.get_versions(plan_id)
        version_num = len(versions) + 1

        # Extract artifact IDs and task descriptions
        artifacts = tuple(execution.graph) if execution.graph else ()
        tasks = tuple(
            execution.graph[aid].description
            for aid in execution.graph
            if hasattr(execution.graph[aid], "description")
        ) if execution.graph else ()

        # Compute diff from previous version
        prev = versions[-1] if versions else None
        diff = self._compute_version_diff(prev, artifacts) if prev else {}

        version = PlanVersion(
            version=version_num,
            plan_id=plan_id,
            goal=execution.goal,
            artifacts=artifacts,
            tasks=tasks,
            score=getattr(execution, "score", None),
            created_at=datetime.now(),
            reason=reason,
            added_artifacts=diff.get("added", ()),
            removed_artifacts=diff.get("removed", ()),
            modified_artifacts=diff.get("modified", ()),
        )

        self._write_version(version)
        return version

    def get_versions(self, plan_id: str) -> list[PlanVersion]:
        """Get all versions of a plan.

        Args:
            plan_id: The plan ID (goal_hash)

        Returns:
            List of PlanVersion objects, ordered by version number
        """
        version_dir = self.base_path / plan_id
        if not version_dir.exists():
            return []

        versions = []
        for vfile in sorted(version_dir.glob("v*.json")):
            try:
                with open(vfile) as f:
                    versions.append(PlanVersion.from_dict(json.load(f)))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(versions, key=lambda v: v.version)

    def get_version(self, plan_id: str, version: int) -> PlanVersion | None:
        """Get a specific version of a plan.

        Args:
            plan_id: The plan ID (goal_hash)
            version: Version number

        Returns:
            PlanVersion or None if not found
        """
        version_path = self.base_path / plan_id / f"v{version}.json"
        if not version_path.exists():
            return None

        with open(version_path) as f:
            return PlanVersion.from_dict(json.load(f))

    def diff(self, plan_id: str, v1: int, v2: int) -> PlanDiff | None:
        """Compute diff between two versions.

        Args:
            plan_id: The plan ID
            v1: First version number
            v2: Second version number

        Returns:
            PlanDiff or None if versions not found
        """
        version1 = self.get_version(plan_id, v1)
        version2 = self.get_version(plan_id, v2)

        if not version1 or not version2:
            return None

        set1 = set(version1.artifacts)
        set2 = set(version2.artifacts)

        return PlanDiff(
            plan_id=plan_id,
            v1=v1,
            v2=v2,
            added=tuple(set2 - set1),
            removed=tuple(set1 - set2),
            modified=(),  # Would need content comparison for true modification
        )

    def _write_version(self, version: PlanVersion) -> Path:
        """Write a version to disk.

        Args:
            version: The version to write

        Returns:
            Path to the written file
        """
        version_dir = self.base_path / version.plan_id
        version_dir.mkdir(parents=True, exist_ok=True)

        version_path = version_dir / f"v{version.version}.json"

        with self._lock:
            temp_path = version_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(version.to_dict(), f, indent=2)
            temp_path.rename(version_path)

        return version_path

    def _compute_version_diff(
        self,
        prev: PlanVersion,
        current_artifacts: tuple[str, ...],
    ) -> dict[str, tuple[str, ...]]:
        """Compute diff between previous version and current artifacts.

        Args:
            prev: Previous version
            current_artifacts: Current artifact IDs

        Returns:
            Dict with 'added', 'removed', 'modified' keys
        """
        prev_set = set(prev.artifacts)
        curr_set = set(current_artifacts)

        return {
            "added": tuple(curr_set - prev_set),
            "removed": tuple(prev_set - curr_set),
            "modified": (),  # Would need deeper comparison
        }
