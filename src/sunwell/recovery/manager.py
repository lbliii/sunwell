"""Recovery state manager (RFC-125).

Handles saving, loading, and listing recovery states. Uses atomic
writes for safety and JSON format for debugging/portability.

Example:
    >>> manager = RecoveryManager(Path(".sunwell/recovery"))
    >>>
    >>> # Save recovery state
    >>> state = manager.create_from_execution(...)
    >>> manager.save(state)
    >>>
    >>> # List pending
    >>> for summary in manager.list_pending():
    ...     print(f"{summary.goal_preview}: {summary.passed}/{summary.total}")
    >>>
    >>> # Load and modify
    >>> state = manager.load("abc123")
    >>> state.mark_fixed("api.py", new_content)
    >>> manager.save(state)
    >>>
    >>> # Mark resolved
    >>> manager.mark_resolved("abc123")
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.recovery.types import (
    ArtifactStatus,
    RecoveryArtifact,
    RecoveryState,
    RecoverySummary,
)

if TYPE_CHECKING:
    from sunwell.agent.validation import Artifact
    from sunwell.convergence.types import ConvergenceIteration


class RecoveryManager:
    """Manages saving and loading recovery state.

    Automatically saves on:
    - Gate failure
    - Convergence escalation
    - Timeout
    - User cancellation

    State files are stored in: {state_dir}/{goal_hash}.json
    Resolved states are moved to: {state_dir}/archive/{goal_hash}.json
    """

    def __init__(self, state_dir: Path):
        """Initialize recovery manager.

        Args:
            state_dir: Directory for recovery state files
        """
        self.state_dir = state_dir
        self.archive_dir = state_dir / "archive"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def create_from_execution(
        self,
        goal: str,
        goal_hash: str,
        run_id: str,
        artifacts: dict[str, Artifact],
        gate_results: dict[str, tuple[bool, list[str]]],
        failure_reason: str,
        iterations: list[ConvergenceIteration] | None = None,
    ) -> RecoveryState:
        """Create recovery state from failed execution.

        Args:
            goal: Original goal text
            goal_hash: Hash of the goal for lookup
            run_id: Unique run identifier
            artifacts: All generated artifacts (path -> Artifact)
            gate_results: Results per artifact (path -> (passed, errors))
            failure_reason: Why the failure occurred
            iterations: Optional convergence iteration history

        Returns:
            RecoveryState ready for saving
        """
        recovery_artifacts: dict[str, RecoveryArtifact] = {}

        # Determine status for each artifact
        for path, artifact in artifacts.items():
            passed, errors = gate_results.get(path, (True, []))

            # Check if blocked by dependency
            is_waiting = False
            if hasattr(artifact, "depends_on"):
                for dep in artifact.depends_on:
                    dep_result = gate_results.get(dep, (True, []))
                    if not dep_result[0]:
                        is_waiting = True
                        break

            if is_waiting:
                status = ArtifactStatus.WAITING
            elif passed:
                status = ArtifactStatus.PASSED
            else:
                status = ArtifactStatus.FAILED

            recovery_artifacts[path] = RecoveryArtifact(
                path=Path(path),
                content=artifact.content,
                status=status,
                errors=tuple(errors),
                depends_on=tuple(getattr(artifact, "depends_on", [])),
            )

        # Collect all error details
        error_details = []
        for path, (passed, errors) in gate_results.items():
            if not passed:
                for err in errors:
                    error_details.append(f"{path}: {err}")

        # Convert iteration history
        iteration_history = []
        if iterations:
            for it in iterations:
                iteration_history.append({
                    "iteration": it.iteration,
                    "all_passed": it.all_passed,
                    "total_errors": it.total_errors,
                    "files_changed": [str(f) for f in it.files_changed],
                })

        return RecoveryState(
            goal=goal,
            goal_hash=goal_hash,
            run_id=run_id,
            artifacts=recovery_artifacts,
            failure_reason=failure_reason,
            error_details=error_details,
            iteration_history=iteration_history,
        )

    def save(self, state: RecoveryState) -> Path:
        """Save recovery state atomically.

        Uses temp file + rename for crash safety.

        Args:
            state: Recovery state to save

        Returns:
            Path to saved file
        """
        target = self.state_dir / f"{state.goal_hash}.json"

        # Serialize to JSON
        data = self._state_to_dict(state)

        # Atomic write: temp file in same dir, then rename
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.state_dir,
            suffix=".tmp",
            delete=False,
        ) as f:
            json.dump(data, f, indent=2, default=str)
            temp_path = Path(f.name)

        temp_path.rename(target)
        return target

    def load(self, goal_hash: str) -> RecoveryState | None:
        """Load recovery state by goal hash.

        Args:
            goal_hash: Hash of the goal

        Returns:
            RecoveryState or None if not found
        """
        path = self.state_dir / f"{goal_hash}.json"
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)

        return self._dict_to_state(data)

    def list_pending(self) -> list[RecoverySummary]:
        """List all pending recoveries (not archived).

        Returns:
            List of RecoverySummary, sorted by creation time (newest first)
        """
        summaries = []

        for path in self.state_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)

                summaries.append(RecoverySummary(
                    goal_hash=data["goal_hash"],
                    goal_preview=data["goal"][:80],
                    run_id=data["run_id"],
                    passed=sum(
                        1 for a in data["artifacts"].values()
                        if a["status"] == "passed"
                    ),
                    failed=sum(
                        1 for a in data["artifacts"].values()
                        if a["status"] == "failed"
                    ),
                    waiting=sum(
                        1 for a in data["artifacts"].values()
                        if a["status"] == "waiting"
                    ),
                    created_at=datetime.fromisoformat(data["created_at"]),
                ))
            except (json.JSONDecodeError, KeyError):
                continue  # Skip malformed files

        # Sort by creation time, newest first
        summaries.sort(key=lambda s: s.created_at, reverse=True)
        return summaries

    def mark_resolved(self, goal_hash: str) -> None:
        """Mark recovery as resolved (move to archive).

        Args:
            goal_hash: Hash of the goal to archive
        """
        source = self.state_dir / f"{goal_hash}.json"
        if not source.exists():
            return

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        target = self.archive_dir / f"{goal_hash}.json"
        source.rename(target)

    def delete(self, goal_hash: str) -> None:
        """Delete recovery state (user aborted).

        Args:
            goal_hash: Hash of the goal to delete
        """
        path = self.state_dir / f"{goal_hash}.json"
        path.unlink(missing_ok=True)

    def _state_to_dict(self, state: RecoveryState) -> dict[str, Any]:
        """Convert RecoveryState to JSON-serializable dict."""
        return {
            "goal": state.goal,
            "goal_hash": state.goal_hash,
            "run_id": state.run_id,
            "artifacts": {
                path: {
                    "path": str(a.path),
                    "content": a.content,
                    "status": a.status.value,
                    "errors": list(a.errors),
                    "depends_on": list(a.depends_on),
                }
                for path, a in state.artifacts.items()
            },
            "failed_gate": state.failed_gate,
            "failure_reason": state.failure_reason,
            "error_details": state.error_details,
            "iteration_history": state.iteration_history,
            "fix_attempts": state.fix_attempts,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
        }

    def _dict_to_state(self, data: dict[str, Any]) -> RecoveryState:
        """Convert dict back to RecoveryState."""
        artifacts = {}
        for path, a in data.get("artifacts", {}).items():
            artifacts[path] = RecoveryArtifact(
                path=Path(a["path"]),
                content=a["content"],
                status=ArtifactStatus(a["status"]),
                errors=tuple(a.get("errors", [])),
                depends_on=tuple(a.get("depends_on", [])),
            )

        return RecoveryState(
            goal=data["goal"],
            goal_hash=data["goal_hash"],
            run_id=data["run_id"],
            artifacts=artifacts,
            failed_gate=data.get("failed_gate"),
            failure_reason=data.get("failure_reason", ""),
            error_details=data.get("error_details", []),
            iteration_history=data.get("iteration_history", []),
            fix_attempts=data.get("fix_attempts", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
