"""Briefing System — Rolling Handoff Notes for Agent Continuity (RFC-071).

The briefing is a compressed "where are we now" that provides instant orientation
at session start. Unlike accumulated learnings (which grow over time), the briefing
is OVERWRITTEN each session, acting as "Twitter for LLMs" where the character
constraint enforces salience.

Key insight: The lossy nature is the feature. Like a game of telephone, each session
compresses what matters, naturally filtering signal from noise.

Extended insight: The briefing isn't just orientation — it's a dispatch signal that
coordinates expensive operations. A tiny model reads the briefing and pre-loads code,
skills, and DAG context before the main agent starts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.foundation.utils import safe_json_dump, safe_json_load

if TYPE_CHECKING:
    pass


class BriefingStatus(Enum):
    """Current state of the work."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class Briefing:
    """Rolling handoff note — overwritten each session.

    This is NOT accumulated history — it's a compressed "where are we now."
    Think: Twitter for LLMs. The constraint enforces salience.

    Design principles:
    1. ~300 tokens max — fits in any context window
    2. Overwritten, not appended — forces compression
    3. Pointers, not content — links to deep memory
    4. Actionable — orientation + momentum + hazards
    """

    # === ORIENTATION (5-second scan) ===
    mission: str
    """What we're trying to accomplish (1 sentence)."""

    status: BriefingStatus
    """Current state: not_started, in_progress, blocked, complete."""

    progress: str
    """Brief summary of where we are (1-2 sentences)."""

    # === MOMENTUM (direction, not just state) ===
    last_action: str
    """What was just done (1 sentence)."""

    next_action: str | None = None
    """What should happen next (1 sentence). None if complete."""

    # === HAZARDS (what NOT to do) ===
    hazards: tuple[str, ...] = field(default_factory=tuple)
    """Things to avoid — max 3, most critical only."""

    # === BLOCKERS (what's preventing progress) ===
    blockers: tuple[str, ...] = field(default_factory=tuple)
    """What's preventing progress. Empty if not blocked."""

    # === FOCUS (where to look) ===
    hot_files: tuple[str, ...] = field(default_factory=tuple)
    """Files currently relevant — max 5."""

    # === DEEP MEMORY POINTERS ===
    goal_hash: str | None = None
    """Links to DAG goal for full history."""

    related_learnings: tuple[str, ...] = field(default_factory=tuple)
    """Learning IDs to pull if more context needed — max 5."""

    # === DISPATCH HINTS (optional, for advanced routing) ===
    predicted_skills: tuple[str, ...] = field(default_factory=tuple)
    """Skills the agent predicted it would need next."""

    suggested_lens: str | None = None
    """Lens that best fits the current work."""

    complexity_estimate: str | None = None
    """Expected complexity: trivial, moderate, complex, requires_human."""

    estimated_files_touched: int | None = None
    """Rough estimate of files that will be modified."""

    # === METADATA ===
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""

    # === METHODS ===

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        data: dict[str, Any] = {
            "mission": self.mission,
            "status": self.status.value,
            "progress": self.progress,
            "last_action": self.last_action,
            "next_action": self.next_action,
            "hazards": list(self.hazards),
            "blockers": list(self.blockers),
            "hot_files": list(self.hot_files),
            "goal_hash": self.goal_hash,
            "related_learnings": list(self.related_learnings),
            "updated_at": self.updated_at,
            "session_id": self.session_id,
        }
        # Optional dispatch hints (only include if set)
        if self.predicted_skills:
            data["predicted_skills"] = list(self.predicted_skills)
        if self.suggested_lens:
            data["suggested_lens"] = self.suggested_lens
        if self.complexity_estimate:
            data["complexity_estimate"] = self.complexity_estimate
        if self.estimated_files_touched is not None:
            data["estimated_files_touched"] = self.estimated_files_touched
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Briefing:
        """Deserialize from JSON."""
        return cls(
            mission=data["mission"],
            status=BriefingStatus(data["status"]),
            progress=data["progress"],
            last_action=data["last_action"],
            next_action=data.get("next_action"),
            hazards=tuple(data.get("hazards", [])),
            blockers=tuple(data.get("blockers", [])),
            hot_files=tuple(data.get("hot_files", [])),
            goal_hash=data.get("goal_hash"),
            related_learnings=tuple(data.get("related_learnings", [])),
            # Dispatch hints
            predicted_skills=tuple(data.get("predicted_skills", [])),
            suggested_lens=data.get("suggested_lens"),
            complexity_estimate=data.get("complexity_estimate"),
            estimated_files_touched=data.get("estimated_files_touched"),
            # Metadata
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            session_id=data.get("session_id", ""),
        )

    def to_prompt(self) -> str:
        """Format for injection into agent system prompt.

        This is what the agent sees at session start.
        Optimized for instant orientation (<5 seconds).
        Uses first-person voice to reduce epistemic distance.
        """
        lines = [
            "## Where I Am (Briefing)",
            "",
            f"**My Mission**: {self.mission}",
            f"**Status**: {self.status.value.replace('_', ' ').title()}",
            f"**Where I am**: {self.progress}",
            "",
            f"**What I just did**: {self.last_action}",
        ]

        if self.next_action:
            lines.append(f"**What I'll do next**: {self.next_action}")

        if self.hazards:
            lines.append("")
            lines.append("**Hazards** (I should avoid):")
            for h in self.hazards:
                lines.append(f"- ⚠️ {h}")

        if self.blockers:
            lines.append("")
            lines.append("**What's blocking me**:")
            for b in self.blockers:
                lines.append(f"- 🚫 {b}")

        if self.hot_files:
            lines.append("")
            lines.append(f"**Files I'm focusing on**: {', '.join(f'`{f}`' for f in self.hot_files)}")

        return "\n".join(lines)

    def save(self, project_path: Path) -> bool:
        """Save briefing to project (OVERWRITES existing).

        Uses atomic write to prevent corruption on crash.

        Returns:
            True if saved successfully, False on error.
        """
        briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"
        return safe_json_dump(self.to_dict(), briefing_path)

    @classmethod
    def load(cls, project_path: Path) -> Briefing | None:
        """Load briefing from project. Returns None if not found or corrupted."""
        briefing_path = project_path / ".sunwell" / "memory" / "briefing.json"
        data = safe_json_load(briefing_path)
        if data is None:
            return None
        return cls.from_dict(data)

    @classmethod
    def create_initial(cls, mission: str, goal_hash: str | None = None) -> Briefing:
        """Create initial briefing for a new goal.

        Uses first-person voice for continuity.
        """
        return cls(
            mission=mission,
            status=BriefingStatus.NOT_STARTED,
            progress="I'm starting fresh.",
            last_action="I received the goal.",
            next_action="I'll begin planning.",
            goal_hash=goal_hash,
        )


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """Summary of what happened during agent execution.

    Built from task graph completion and agent state.
    Used to generate the next briefing at session end.
    """

    last_action: str
    """What was accomplished this session (1 sentence)."""

    next_action: str | None
    """What should happen next (None if complete)."""

    modified_files: tuple[str, ...]
    """Files that were created or modified."""

    tasks_completed: int
    """Number of tasks completed."""

    gates_passed: int
    """Number of quality gates passed."""

    new_learnings: tuple[str, ...]
    """Learning IDs generated this session."""

    new_hazards: tuple[str, ...] = field(default_factory=tuple)
    """Hazards discovered this session."""

    resolved_hazards: tuple[str, ...] = field(default_factory=tuple)
    """Hazards that were addressed this session."""

    @classmethod
    def from_task_graph(cls, task_graph: Any, learnings: list[Any]) -> ExecutionSummary:
        """Build summary from completed task graph."""
        completed = task_graph.completed_ids if hasattr(task_graph, "completed_ids") else set()
        gates = task_graph.gates if hasattr(task_graph, "gates") else []

        # Convert set to list for processing
        completed_list = list(completed) if isinstance(completed, set) else completed

        # Determine last action from completed tasks
        if completed_list:
            last_action = f"Completed {len(completed_list)} task(s): {', '.join(completed_list[:3])}"
            if len(completed_list) > 3:
                last_action += f" and {len(completed_list) - 3} more"
        else:
            last_action = "No tasks completed."

        # Determine next action from pending tasks
        pending = []
        if hasattr(task_graph, "tasks"):
            pending = [t.id for t in task_graph.tasks if t.id not in completed]
        next_action = f"Continue with: {pending[0]}" if pending else None

        # Collect modified files from task outputs
        modified: list[str] = []
        if hasattr(task_graph, "tasks"):
            for task in task_graph.tasks:
                if task.id in completed:
                    if hasattr(task, "target_path") and task.target_path:
                        modified.append(str(task.target_path))

        return cls(
            last_action=last_action,
            next_action=next_action,
            modified_files=tuple(modified[:10]),  # Limit to 10
            tasks_completed=len(completed_list),
            gates_passed=len([g for g in gates if hasattr(g, "passed") and g.passed]),
            new_learnings=tuple(getattr(lrn, "id", str(i)) for i, lrn in enumerate(learnings[:5])),
            new_hazards=(),  # Populated by agent
            resolved_hazards=(),  # Populated by agent
        )
