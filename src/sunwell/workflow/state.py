"""Workflow State — Persistent state management (RFC-086).

State is stored in `.sunwell/state/{branch}/{topic}.json` and supports:
- Atomic writes (temp file + rename)
- Git branch isolation
- Resume across sessions
"""


import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.workflow.types import (
    WorkflowChain,
    WorkflowExecution,
    WorkflowStepResult,
)


def _slugify(text: str) -> str:
    """Convert text to filesystem-safe slug.

    Args:
        text: Input text (e.g., "feature/auth-v2")

    Returns:
        Slugified text (e.g., "feature-auth-v2")
    """
    # Replace common separators with dash
    slug = text.replace("/", "-").replace("\\", "-").replace(" ", "-")
    # Remove any characters that aren't alphanumeric or dash
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    # Collapse multiple dashes
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-").lower()


def _get_git_branch() -> str:
    """Get current Git branch name.

    Returns:
        Branch name or "main" if not in a Git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "main"


@dataclass
class WorkflowState:
    """Serializable workflow state for persistence.

    This is the on-disk format stored in `.sunwell/state/{branch}/{topic}.json`.
    """

    version: int = 1
    """Schema version for forward compatibility."""

    id: str = ""
    """Execution ID: "wf-2026-01-21-batch-api"."""

    topic: str = ""
    """Human-readable topic: "Batch API Documentation"."""

    chain_name: str = ""
    """Workflow chain name: "feature-docs"."""

    current_step: int = 0
    """Current step index (0-based)."""

    started_at: str = ""
    """ISO timestamp when started."""

    updated_at: str = ""
    """ISO timestamp of last update."""

    completed_steps: list[dict[str, Any]] = field(default_factory=list)
    """Serialized completed step results."""

    pending_steps: list[str] = field(default_factory=list)
    """Skill names of pending steps."""

    # Context
    lens: str | None = None
    """Active lens name."""

    target_file: str | None = None
    """Target file path."""

    working_dir: str = ""
    """Working directory."""

    status: str = "paused"
    """Execution status."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "id": self.id,
            "topic": self.topic,
            "chain": self.chain_name,
            "currentStep": self.current_step,
            "startedAt": self.started_at,
            "updatedAt": self.updated_at,
            "completedSteps": self.completed_steps,
            "pendingSteps": self.pending_steps,
            "context": {
                "lens": self.lens,
                "target_file": self.target_file,
                "working_dir": self.working_dir,
            },
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowState:
        """Create from dictionary."""
        context = data.get("context", {})
        return cls(
            version=data.get("version", 1),
            id=data.get("id", ""),
            topic=data.get("topic", ""),
            chain_name=data.get("chain", ""),
            current_step=data.get("currentStep", 0),
            started_at=data.get("startedAt", ""),
            updated_at=data.get("updatedAt", ""),
            completed_steps=data.get("completedSteps", []),
            pending_steps=data.get("pendingSteps", []),
            lens=context.get("lens"),
            target_file=context.get("target_file"),
            working_dir=context.get("working_dir", ""),
            status=data.get("status", "paused"),
        )

    @classmethod
    def from_execution(cls, execution: WorkflowExecution, topic: str = "") -> WorkflowState:
        """Create from a WorkflowExecution.

        Args:
            execution: The execution to convert
            topic: Human-readable topic name

        Returns:
            WorkflowState ready for persistence
        """
        pending_skills = [
            step.skill
            for step in execution.chain.steps[execution.current_step + 1:]
        ]

        return cls(
            id=execution.id,
            topic=topic or execution.chain.description,
            chain_name=execution.chain.name,
            current_step=execution.current_step,
            started_at=execution.started_at.isoformat(),
            updated_at=execution.updated_at.isoformat(),
            completed_steps=[s.to_dict() for s in execution.completed_steps],
            pending_steps=pending_skills,
            lens=execution.context.get("lens"),
            target_file=execution.context.get("target_file"),
            working_dir=execution.context.get("working_dir", ""),
            status=execution.status,
        )

    def to_execution(self, chain: WorkflowChain) -> WorkflowExecution:
        """Convert back to WorkflowExecution.

        Args:
            chain: The workflow chain (must match chain_name)

        Returns:
            WorkflowExecution ready to resume
        """
        # Reconstruct step results
        completed = []
        for step_data in self.completed_steps:
            completed.append(
                WorkflowStepResult(
                    skill=step_data["skill"],
                    status=step_data["status"],
                    started_at=datetime.fromisoformat(step_data["started_at"]),
                    completed_at=(
                        datetime.fromisoformat(step_data["completed_at"])
                        if step_data.get("completed_at")
                        else None
                    ),
                    output=step_data.get("output", {}),
                    error=step_data.get("error"),
                )
            )

        return WorkflowExecution(
            id=self.id,
            chain=chain,
            current_step=self.current_step,
            completed_steps=completed,
            status=self.status,  # type: ignore
            started_at=datetime.fromisoformat(self.started_at) if self.started_at else datetime.now(),
            updated_at=datetime.fromisoformat(self.updated_at) if self.updated_at else datetime.now(),
            context={
                "lens": self.lens,
                "target_file": self.target_file,
                "working_dir": self.working_dir,
            },
        )


class WorkflowStateManager:
    """Manages workflow state persistence.

    State is stored per Git branch to isolate concurrent work:
    `.sunwell/state/{branch}/{execution_id}.json`

    Example:
        >>> manager = WorkflowStateManager(Path(".sunwell/state"))
        >>> await manager.save(execution)
        >>> state = await manager.load("wf-2026-01-21-batch-api")
    """

    def __init__(self, state_dir: Path):
        """Initialize the state manager.

        Args:
            state_dir: Root directory for state files
        """
        self.state_dir = state_dir

    def _get_branch_dir(self) -> Path:
        """Get the directory for the current Git branch."""
        branch = _get_git_branch()
        branch_slug = _slugify(branch)
        return self.state_dir / branch_slug

    def _get_state_path(self, execution_id: str) -> Path:
        """Get the path for an execution's state file."""
        return self._get_branch_dir() / f"{execution_id}.json"

    async def save(self, execution: WorkflowExecution, topic: str = "") -> Path:
        """Save execution state to disk.

        Uses atomic write (temp file + rename) for safety.

        Args:
            execution: Execution to save
            topic: Human-readable topic name

        Returns:
            Path to the state file
        """
        state = WorkflowState.from_execution(execution, topic)
        branch_dir = self._get_branch_dir()

        # Ensure directory exists
        branch_dir.mkdir(parents=True, exist_ok=True)

        state_path = self._get_state_path(execution.id)

        # Atomic write: temp file + rename
        fd, temp_path = tempfile.mkstemp(
            dir=branch_dir,
            prefix=".tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            # Atomic rename
            os.rename(temp_path, state_path)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        return state_path

    async def load(self, execution_id: str) -> WorkflowState | None:
        """Load execution state from disk.

        Args:
            execution_id: Execution ID to load

        Returns:
            WorkflowState or None if not found
        """
        state_path = self._get_state_path(execution_id)

        if not state_path.exists():
            # Try other branches
            for branch_dir in self.state_dir.iterdir():
                if branch_dir.is_dir():
                    alt_path = branch_dir / f"{execution_id}.json"
                    if alt_path.exists():
                        state_path = alt_path
                        break
            else:
                return None

        try:
            with open(state_path) as f:
                data = json.load(f)
            return WorkflowState.from_dict(data)
        except (json.JSONDecodeError, OSError):
            return None

    async def list_active(self) -> list[WorkflowState]:
        """List all active (non-completed) workflows.

        Returns:
            List of WorkflowState objects
        """
        states = []
        branch_dir = self._get_branch_dir()

        if not branch_dir.exists():
            return states

        for state_file in branch_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    data = json.load(f)
                state = WorkflowState.from_dict(data)
                if state.status not in ("completed", "cancelled"):
                    states.append(state)
            except (json.JSONDecodeError, OSError):
                continue

        return states

    async def list_all(self) -> list[WorkflowState]:
        """List all workflows for the current branch.

        Returns:
            List of WorkflowState objects
        """
        states = []
        branch_dir = self._get_branch_dir()

        if not branch_dir.exists():
            return states

        for state_file in branch_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    data = json.load(f)
                states.append(WorkflowState.from_dict(data))
            except (json.JSONDecodeError, OSError):
                continue

        return sorted(states, key=lambda s: s.updated_at, reverse=True)

    async def delete(self, execution_id: str) -> bool:
        """Delete a state file.

        Args:
            execution_id: Execution ID to delete

        Returns:
            True if deleted, False if not found
        """
        state_path = self._get_state_path(execution_id)

        if state_path.exists():
            state_path.unlink()
            return True
        return False

    async def cleanup_completed(self, max_age_days: int = 7) -> int:
        """Clean up old completed workflows.

        Args:
            max_age_days: Delete completed workflows older than this

        Returns:
            Number of files deleted
        """
        deleted = 0
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)

        branch_dir = self._get_branch_dir()
        if not branch_dir.exists():
            return 0

        for state_file in branch_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    data = json.load(f)
                state = WorkflowState.from_dict(data)

                if state.status == "completed":
                    updated = datetime.fromisoformat(state.updated_at)
                    if updated.timestamp() < cutoff:
                        state_file.unlink()
                        deleted += 1
            except (json.JSONDecodeError, OSError, ValueError):
                continue

        return deleted
