"""Backlog Management for Autonomous Backlog (RFC-046 Phase 3).

Maintain goal DAG and coordinate execution.

RFC-051 Extensions:
- claim_goal(goal_id, worker_id) - Claim a goal for multi-instance
- exclusive_access() - Context manager for cross-process safety
- get_pending_goals() - Get unclaimed, incomplete goals
- mark_failed(goal_id, error) - Mark a goal as failed
- get_goal(goal_id) - Get a goal by ID
"""


import contextlib
import fcntl
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult, GoalScope
from sunwell.backlog.signals import SignalExtractor

if TYPE_CHECKING:
    from sunwell.intelligence.context import ProjectContext


@dataclass(slots=True)
class Backlog:
    """The prioritized backlog as an artifact DAG."""

    goals: dict[str, Goal]
    """All known goals."""

    completed: set[str]
    """Goal IDs that are done."""

    in_progress: str | None
    """Currently executing goal, if any."""

    blocked: dict[str, str]
    """Goal ID → reason blocked."""

    # RFC-115: Hierarchical Goal Decomposition fields
    active_epic: str | None = None
    """Currently executing epic."""

    active_milestone: str | None = None
    """Currently executing milestone within active epic."""

    def execution_order(self) -> list[Goal]:
        """Return goals in optimal execution order.

        Uses same wave algorithm as ArtifactGraph (RFC-036):
        - Leaves first (no dependencies)
        - Higher priority within each wave
        - Quick wins before complex tasks
        """
        completed_set = self.completed | set(self.blocked.keys())

        # Topological sort with priority ordering
        waves: list[list[Goal]] = []
        remaining = {
            g.id: g
            for g in self.goals.values()
            if g.id not in completed_set
        }

        while remaining:
            # Find leaves (no uncompleted dependencies)
            ready = [
                g
                for g in remaining.values()
                if all(dep in completed_set for dep in g.requires)
            ]

            if not ready:
                # Cycle or missing dependency - add remaining in priority order
                ready = sorted(
                    remaining.values(),
                    key=lambda g: g.priority,
                    reverse=True,
                )[:1]

            # Sort by priority within wave
            ready_sorted = sorted(ready, key=lambda g: g.priority, reverse=True)
            waves.append(ready_sorted)

            # Mark as completed for next wave
            for g in ready_sorted:
                completed_set.add(g.id)
                remaining.pop(g.id, None)

        # Flatten waves
        return [g for wave in waves for g in wave]

    def next_goal(self) -> Goal | None:
        """Get the next goal to work on."""
        for goal in self.execution_order():
            if goal.id not in self.completed:
                if goal.id not in self.blocked:
                    if all(dep in self.completed for dep in goal.requires):
                        return goal
        return None

    def to_mermaid(self) -> str:
        """Export backlog as Mermaid diagram."""
        lines = ["graph TD"]
        goal_map = {g.id: g for g in self.goals.values()}

        for goal in self.goals.values():
            status = "✓" if goal.id in self.completed else "⏳" if goal.id == self.in_progress else "□"
            lines.append(f'  {goal.id}["{status} {goal.title[:30]}"]')

        for goal in self.goals.values():
            for dep_id in goal.requires:
                if dep_id in goal_map:
                    lines.append(f"  {dep_id} --> {goal.id}")

        return "\n".join(lines)

    # =========================================================================
    # RFC-115: Hierarchy Methods
    # =========================================================================

    def get_epic(self, epic_id: str) -> Goal | None:
        """Get epic by ID (RFC-115)."""
        goal = self.goals.get(epic_id)
        if goal and goal.goal_type == "epic":
            return goal
        return None

    def get_milestones(self, epic_id: str) -> list[Goal]:
        """Get all milestones for an epic, sorted by milestone_index (RFC-115)."""
        milestones = [
            g for g in self.goals.values()
            if g.goal_type == "milestone" and g.parent_goal_id == epic_id
        ]
        return sorted(milestones, key=lambda g: g.milestone_index or 0)

    def get_tasks_for_milestone(self, milestone_id: str) -> list[Goal]:
        """Get all tasks for a milestone (RFC-115)."""
        return [
            g for g in self.goals.values()
            if g.goal_type == "task" and g.parent_goal_id == milestone_id
        ]

    def get_current_milestone(self) -> Goal | None:
        """Get the milestone currently being executed (RFC-115)."""
        if self.active_milestone:
            return self.goals.get(self.active_milestone)
        return None

    def get_milestone_progress(self, milestone_id: str) -> tuple[int, int]:
        """Get (completed_tasks, total_tasks) for a milestone (RFC-115)."""
        tasks = self.get_tasks_for_milestone(milestone_id)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.id in self.completed)
        return completed, total

    def get_epic_progress(self, epic_id: str) -> tuple[int, int]:
        """Get (completed_milestones, total_milestones) for an epic (RFC-115)."""
        milestones = self.get_milestones(epic_id)
        total = len(milestones)
        completed = sum(1 for m in milestones if m.id in self.completed)
        return completed, total

    def get_next_milestone(self, epic_id: str) -> Goal | None:
        """Get next uncompleted milestone for an epic (RFC-115)."""
        for milestone in self.get_milestones(epic_id):
            if milestone.id not in self.completed and milestone.id not in self.blocked:
                return milestone
        return None


class BacklogManager:
    """Manages the autonomous backlog lifecycle."""

    def __init__(
        self,
        root: Path,
        context: ProjectContext | None = None,
        signal_extractor: SignalExtractor | None = None,
        goal_generator: GoalGenerator | None = None,
        policy: GoalPolicy | None = None,
    ):
        """Initialize backlog manager.

        Args:
            root: Project root directory
            context: Optional project context (for intelligence)
            signal_extractor: Signal extractor (creates if None)
            goal_generator: Goal generator (creates if None)
            policy: Goal policy
        """
        self.root = Path(root)
        self.context = context
        self.policy = policy or GoalPolicy()

        self.signal_extractor = signal_extractor or SignalExtractor(self.root)
        self.goal_generator = goal_generator or GoalGenerator(
            context=context,
            policy=self.policy,
        )

        self.backlog_path = self.root / ".sunwell" / "backlog"
        self.backlog_path.mkdir(parents=True, exist_ok=True)

        self.backlog = Backlog(
            goals={},
            completed=set(),
            in_progress=None,
            blocked={},
            active_epic=None,
            active_milestone=None,
        )

        # External ref index for deduplication (RFC-049)
        self._external_refs: dict[str, str] = {}  # external_ref → goal_id

        # Load existing backlog
        self._load()

    async def refresh(self) -> Backlog:
        """Refresh backlog from current project state.

        Called:
        - On session start
        - After completing a goal
        - After external changes (git pull, etc.)
        """
        # 1. Extract fresh signals
        observable = await self.signal_extractor.extract_all()

        # 2. Generate goals
        intelligence_signals = []
        if self.context:
            # Future: extract intelligence signals from context (RFC-045)
            pass

        goals = await self.goal_generator.generate(
            observable_signals=observable,
            intelligence_signals=intelligence_signals,
        )

        # 3. Merge with existing backlog (preserve completed, update priorities)
        self.backlog = self._merge_backlog(self.backlog, goals)

        # 4. Save
        self._save()

        return self.backlog

    def _merge_backlog(self, existing: Backlog, new_goals: list[Goal]) -> Backlog:
        """Merge new goals with existing backlog.

        Preserves completed goals, updates priorities for existing goals.
        """
        merged_goals: dict[str, Goal] = {}

        # Keep completed goals (for history)
        for goal_id, goal in existing.goals.items():
            if goal_id in existing.completed:
                merged_goals[goal_id] = goal

        # Add/update new goals
        for goal in new_goals:
            if goal.id in merged_goals:
                # Update priority if higher
                existing_goal = merged_goals[goal.id]
                if goal.priority > existing_goal.priority:
                    merged_goals[goal.id] = goal
            else:
                merged_goals[goal.id] = goal

        return Backlog(
            goals=merged_goals,
            completed=existing.completed.copy(),
            in_progress=existing.in_progress,
            blocked=existing.blocked.copy(),
            active_epic=existing.active_epic,
            active_milestone=existing.active_milestone,
        )

    async def complete_goal(self, goal_id: str, result: GoalResult) -> None:
        """Mark a goal as completed and refresh."""
        self.backlog.completed.add(goal_id)
        self.backlog.in_progress = None

        # Record in history
        await self._record_completion(goal_id, result)

        # Refresh to find newly unblocked goals
        await self.refresh()

    async def block_goal(self, goal_id: str, reason: str) -> None:
        """Mark a goal as blocked."""
        self.backlog.blocked[goal_id] = reason
        self.backlog.in_progress = None
        self._save()

    async def add_external_goal(self, goal: Goal) -> None:
        """Add a goal from an external event (RFC-049).

        External goals are:
        1. Tracked with external_ref for deduplication
        2. Prioritized alongside internal goals
        3. Logged separately for auditing

        Args:
            goal: The goal to add (must have external_ref set)
        """
        self.backlog.goals[goal.id] = goal

        # Track external reference for deduplication
        if goal.external_ref:
            self._external_refs[goal.external_ref] = goal.id

        self._save()

    async def get_goals_by_external_ref(self, ref: str) -> list[Goal]:
        """Get goals associated with an external reference (RFC-049).

        Args:
            ref: External reference ID (e.g., 'github:issue:123')

        Returns:
            List of goals with this external reference (usually 0 or 1)
        """
        goal_id = self._external_refs.get(ref)
        if goal_id and goal_id in self.backlog.goals:
            return [self.backlog.goals[goal_id]]
        return []

    # =========================================================================
    # RFC-051: Multi-Instance Coordination Methods
    # =========================================================================

    @asynccontextmanager
    async def exclusive_access(self) -> AsyncIterator[None]:
        """Acquire exclusive access to backlog.

        Uses flock for cross-process safety. Must be used when
        modifying backlog from multiple worker processes.

        Example:
            async with backlog_manager.exclusive_access():
                goal = await backlog_manager.get_pending_goals()[0]
                await backlog_manager.claim_goal(goal.id, worker_id=1)
        """
        lock_path = self.backlog_path / "backlog.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # Reload to get latest state
            self._load()
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    async def claim_goal(self, goal_id: str, worker_id: int | None = None) -> bool:
        """Claim a goal for a worker (RFC-051, RFC-094).

        Must be called within exclusive_access() context for multi-instance.
        Single-instance execution can pass worker_id=None (uses -1 sentinel).

        Args:
            goal_id: ID of the goal to claim
            worker_id: ID of the claiming worker (None for single-instance)

        Returns:
            True if successfully claimed, False if already claimed
        """
        goal = self.backlog.goals.get(goal_id)
        if goal is None:
            return False

        # Check if already claimed
        if goal.claimed_by is not None:
            return False

        # For single-instance, use -1 as sentinel
        effective_worker_id = worker_id if worker_id is not None else -1

        # Create new goal with claim info
        claimed_goal = Goal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            source_signals=goal.source_signals,
            priority=goal.priority,
            estimated_complexity=goal.estimated_complexity,
            requires=goal.requires,
            category=goal.category,
            auto_approvable=goal.auto_approvable,
            scope=goal.scope,
            external_ref=goal.external_ref,
            claimed_by=effective_worker_id,
            claimed_at=datetime.now(),
        )

        self.backlog.goals[goal_id] = claimed_goal
        self._save()
        return True

    async def get_pending_goals(self) -> list[Goal]:
        """Get goals that are pending (not completed, not blocked).

        For multi-instance, this returns goals in execution order
        that haven't been completed or blocked.

        Returns:
            List of pending goals in priority order
        """
        pending = []
        for goal in self.backlog.execution_order():
            if goal.id not in self.backlog.completed and goal.id not in self.backlog.blocked:
                pending.append(goal)
        return pending

    async def get_goal(self, goal_id: str) -> Goal | None:
        """Get a goal by ID.

        Args:
            goal_id: ID of the goal to retrieve

        Returns:
            The goal, or None if not found
        """
        return self.backlog.goals.get(goal_id)

    async def mark_complete(self, goal_id: str) -> None:
        """Mark a goal as completed (RFC-051).

        Args:
            goal_id: ID of the goal to mark complete
        """
        self.backlog.completed.add(goal_id)
        self.backlog.in_progress = None
        self._save()

    async def mark_failed(self, goal_id: str, error: str) -> None:
        """Mark a goal as failed (RFC-051).

        Args:
            goal_id: ID of the goal that failed
            error: Error message describing the failure
        """
        self.backlog.blocked[goal_id] = f"Failed: {error}"
        self.backlog.in_progress = None
        self._save()

    async def unclaim_goal(self, goal_id: str) -> None:
        """Remove claim from a goal (RFC-051).

        Used when a worker fails or abandons a goal.

        Args:
            goal_id: ID of the goal to unclaim
        """
        goal = self.backlog.goals.get(goal_id)
        if goal is None:
            return

        # Create new goal without claim
        unclaimed_goal = Goal(
            id=goal.id,
            title=goal.title,
            description=goal.description,
            source_signals=goal.source_signals,
            priority=goal.priority,
            estimated_complexity=goal.estimated_complexity,
            requires=goal.requires,
            category=goal.category,
            auto_approvable=goal.auto_approvable,
            scope=goal.scope,
            external_ref=goal.external_ref,
            claimed_by=None,
            claimed_at=None,
        )

        self.backlog.goals[goal_id] = unclaimed_goal
        self._save()

    def get_claims(self) -> dict[str, int]:
        """Get current goal claims (RFC-051).

        Returns:
            Dictionary mapping goal_id → worker_id for claimed goals
        """
        claims = {}
        for goal in self.backlog.goals.values():
            if goal.claimed_by is not None:
                claims[goal.id] = goal.claimed_by
        return claims

    # =========================================================================
    # RFC-115: Hierarchical Goal Decomposition Methods
    # =========================================================================

    async def add_epic(self, epic: Goal) -> None:
        """Add an epic to the backlog (RFC-115).

        Args:
            epic: The epic goal (must have goal_type="epic")
        """
        if epic.goal_type != "epic":
            msg = f"Expected epic, got {epic.goal_type}"
            raise ValueError(msg)

        self.backlog.goals[epic.id] = epic
        self._save()

    async def add_milestones(self, milestones: list[Goal]) -> None:
        """Add milestones for an epic (RFC-115).

        Args:
            milestones: List of milestone goals (must have goal_type="milestone")
        """
        for milestone in milestones:
            if milestone.goal_type != "milestone":
                msg = f"Expected milestone, got {milestone.goal_type}"
                raise ValueError(msg)
            self.backlog.goals[milestone.id] = milestone
        self._save()

    async def activate_epic(self, epic_id: str) -> bool:
        """Activate an epic for execution (RFC-115).

        Sets active_epic and activates the first milestone.

        Args:
            epic_id: ID of the epic to activate

        Returns:
            True if activated, False if epic not found
        """
        epic = self.backlog.get_epic(epic_id)
        if epic is None:
            return False

        self.backlog.active_epic = epic_id

        # Activate first milestone
        first_milestone = self.backlog.get_next_milestone(epic_id)
        if first_milestone:
            self.backlog.active_milestone = first_milestone.id

        self._save()
        return True

    async def advance_milestone(self) -> Goal | None:
        """Mark current milestone complete and advance to next (RFC-115).

        Returns:
            The next milestone, or None if epic is complete
        """
        if not self.backlog.active_epic or not self.backlog.active_milestone:
            return None

        # Mark current milestone complete
        self.backlog.completed.add(self.backlog.active_milestone)

        # Find next milestone
        next_milestone = self.backlog.get_next_milestone(self.backlog.active_epic)

        if next_milestone:
            self.backlog.active_milestone = next_milestone.id
        else:
            # Epic complete
            self.backlog.completed.add(self.backlog.active_epic)
            self.backlog.active_epic = None
            self.backlog.active_milestone = None

        self._save()
        return next_milestone

    async def skip_milestone(self) -> Goal | None:
        """Skip current milestone without completing (RFC-115).

        Returns:
            The next milestone, or None if epic has no more milestones
        """
        if not self.backlog.active_epic or not self.backlog.active_milestone:
            return None

        # Block current milestone as skipped
        self.backlog.blocked[self.backlog.active_milestone] = "Skipped by user"

        # Find next milestone
        next_milestone = self.backlog.get_next_milestone(self.backlog.active_epic)

        if next_milestone:
            self.backlog.active_milestone = next_milestone.id
        else:
            # No more milestones
            self.backlog.active_epic = None
            self.backlog.active_milestone = None

        self._save()
        return next_milestone

    async def add_tasks_for_milestone(
        self,
        milestone_id: str,
        tasks: list[Goal],
    ) -> None:
        """Add tasks for a milestone (RFC-115).

        Called when HarmonicPlanner generates tasks for the active milestone.

        Args:
            milestone_id: ID of the milestone
            tasks: List of task goals (will have parent_goal_id set)
        """
        for task in tasks:
            # Ensure task has correct parent
            if task.parent_goal_id != milestone_id:
                # Create new task with correct parent
                task = Goal(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    source_signals=task.source_signals,
                    priority=task.priority,
                    estimated_complexity=task.estimated_complexity,
                    requires=task.requires,
                    category=task.category,
                    auto_approvable=task.auto_approvable,
                    scope=task.scope,
                    external_ref=task.external_ref,
                    claimed_by=task.claimed_by,
                    claimed_at=task.claimed_at,
                    produces=task.produces,
                    integrations=task.integrations,
                    verification_checks=task.verification_checks,
                    task_type=task.task_type,
                    goal_type="task",
                    parent_goal_id=milestone_id,
                    milestone_produces=(),
                    milestone_index=None,
                )
            self.backlog.goals[task.id] = task

        self._save()

    def get_epic_status(self, epic_id: str) -> dict:
        """Get comprehensive status for an epic (RFC-115).

        Returns dict with:
        - epic: Goal
        - milestones: list[Goal]
        - completed_milestones: int
        - total_milestones: int
        - current_milestone: Goal | None
        - current_milestone_tasks: int
        - current_milestone_completed_tasks: int
        """
        epic = self.backlog.get_epic(epic_id)
        if not epic:
            return {}

        milestones = self.backlog.get_milestones(epic_id)
        completed, total = self.backlog.get_epic_progress(epic_id)
        current = self.backlog.get_current_milestone()

        current_tasks = 0
        current_completed = 0
        if current and current.parent_goal_id == epic_id:
            current_completed, current_tasks = self.backlog.get_milestone_progress(
                current.id
            )

        return {
            "epic": epic,
            "milestones": milestones,
            "completed_milestones": completed,
            "total_milestones": total,
            "current_milestone": current,
            "current_milestone_tasks": current_tasks,
            "current_milestone_completed_tasks": current_completed,
        }

    async def _record_completion(self, goal_id: str, result: GoalResult) -> None:
        """Record goal completion in history."""
        history_path = self.backlog_path / "completed.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "goal_id": goal_id,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
            "files_changed": result.files_changed,
            "failure_reason": result.failure_reason,
            "artifacts_created": result.artifacts_created,  # RFC-094
            "timestamp": datetime.now().isoformat(),
        }

        with history_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    async def get_completed_artifacts(self) -> list[str]:
        """Get list of artifact IDs from completed goals (RFC-094).

        Reads from completion history to find all artifacts created.

        Returns:
            List of artifact IDs that were successfully created
        """
        history_path = self.backlog_path / "completed.jsonl"
        if not history_path.exists():
            return []

        artifacts: list[str] = []
        for line in history_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                artifacts.extend(entry.get("artifacts_created", []))
            except json.JSONDecodeError:
                continue

        return artifacts

    async def get_related_goals(
        self,
        goal_id: str | None = None,
        artifact_id: str | None = None,
    ) -> list[dict]:
        """Find goals related by shared artifacts (RFC-094).

        This powers "show related goals" UI feature. Goals are related if they:
        - Created the same artifact (same file path)
        - Share artifact dependencies

        Args:
            goal_id: Find goals related to this goal
            artifact_id: Find goals that created this artifact

        Returns:
            List of related goal info dicts with:
            - goal_id: str
            - title: str
            - relationship: "created_same_artifact" | "shares_dependency"
            - shared_artifacts: list[str]
        """
        history_path = self.backlog_path / "completed.jsonl"
        if not history_path.exists():
            return []

        # Build artifact→goals index
        artifact_to_goals: dict[str, list[dict]] = {}
        goal_to_artifacts: dict[str, list[str]] = {}

        for line in history_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                gid = entry.get("goal_id", "")
                artifacts = entry.get("artifacts_created", [])

                goal_to_artifacts[gid] = artifacts
                for aid in artifacts:
                    if aid not in artifact_to_goals:
                        artifact_to_goals[aid] = []
                    artifact_to_goals[aid].append({
                        "goal_id": gid,
                        "timestamp": entry.get("timestamp"),
                    })
            except json.JSONDecodeError:
                continue

        related: list[dict] = []
        seen_goals: set[str] = set()

        # Find goals that created the specified artifact
        if artifact_id and artifact_id in artifact_to_goals:
            for info in artifact_to_goals[artifact_id]:
                gid = info["goal_id"]
                if gid not in seen_goals:
                    seen_goals.add(gid)
                    goal = self.backlog.goals.get(gid)
                    related.append({
                        "goal_id": gid,
                        "title": goal.title if goal else gid,
                        "relationship": "created_artifact",
                        "shared_artifacts": [artifact_id],
                    })

        # Find goals related to the specified goal
        if goal_id:
            target_artifacts = set(goal_to_artifacts.get(goal_id, []))
            for gid, artifacts in goal_to_artifacts.items():
                if gid == goal_id or gid in seen_goals:
                    continue

                shared = target_artifacts & set(artifacts)
                if shared:
                    seen_goals.add(gid)
                    goal = self.backlog.goals.get(gid)
                    related.append({
                        "goal_id": gid,
                        "title": goal.title if goal else gid,
                        "relationship": "created_same_artifact",
                        "shared_artifacts": list(shared),
                    })

        return related

    def _load(self) -> None:
        """Load backlog from disk."""
        current_path = self.backlog_path / "current.json"
        if not current_path.exists():
            return

        try:
            data = json.loads(current_path.read_text())
            goals: dict[str, Goal] = {}

            for gid, goal_data in data.get("goals", {}).items():
                # Reconstruct Goal with proper types
                scope_data = goal_data.get("scope", {})
                scope = GoalScope(
                    max_files=scope_data.get("max_files", 5),
                    max_lines_changed=scope_data.get("max_lines_changed", 500),
                )

                # RFC-051: Parse claimed_at timestamp
                claimed_at = None
                if goal_data.get("claimed_at"):
                    with contextlib.suppress(ValueError, TypeError):
                        claimed_at = datetime.fromisoformat(goal_data["claimed_at"])

                goals[gid] = Goal(
                    id=goal_data["id"],
                    title=goal_data["title"],
                    description=goal_data["description"],
                    source_signals=tuple(goal_data.get("source_signals", [])),
                    priority=goal_data["priority"],
                    estimated_complexity=goal_data["estimated_complexity"],
                    requires=frozenset(goal_data.get("requires", [])),
                    category=goal_data["category"],
                    auto_approvable=goal_data.get("auto_approvable", False),
                    scope=scope,
                    external_ref=goal_data.get("external_ref"),  # RFC-049
                    claimed_by=goal_data.get("claimed_by"),  # RFC-051
                    claimed_at=claimed_at,  # RFC-051
                    # RFC-115: Hierarchy fields
                    goal_type=goal_data.get("goal_type", "task"),
                    parent_goal_id=goal_data.get("parent_goal_id"),
                    milestone_produces=tuple(goal_data.get("milestone_produces", [])),
                    milestone_index=goal_data.get("milestone_index"),
                )

            self.backlog = Backlog(
                goals=goals,
                completed=set(data.get("completed", [])),
                in_progress=data.get("in_progress"),
                blocked=data.get("blocked", {}),
                active_epic=data.get("active_epic"),  # RFC-115
                active_milestone=data.get("active_milestone"),  # RFC-115
            )

            # Load or rebuild external refs index (RFC-049)
            self._external_refs = data.get("external_refs", {})
            if not self._external_refs:
                # Rebuild index from goals if migrating from old schema
                for goal in self.backlog.goals.values():
                    if goal.external_ref:
                        self._external_refs[goal.external_ref] = goal.id

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Invalid data - start fresh
            pass

    def _save(self) -> None:
        """Save backlog to disk."""
        current_path = self.backlog_path / "current.json"
        current_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "schema_version": 4,  # RFC-115: Added hierarchy fields
            "goals": {
                gid: {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "source_signals": list(goal.source_signals),
                    "priority": goal.priority,
                    "estimated_complexity": goal.estimated_complexity,
                    "requires": list(goal.requires),
                    "category": goal.category,
                    "auto_approvable": goal.auto_approvable,
                    "scope": {
                        "max_files": goal.scope.max_files,
                        "max_lines_changed": goal.scope.max_lines_changed,
                    },
                    "external_ref": goal.external_ref,  # RFC-049
                    "claimed_by": goal.claimed_by,  # RFC-051
                    "claimed_at": (
                        goal.claimed_at.isoformat() if goal.claimed_at else None
                    ),  # RFC-051
                    # RFC-115: Hierarchy fields
                    "goal_type": goal.goal_type,
                    "parent_goal_id": goal.parent_goal_id,
                    "milestone_produces": list(goal.milestone_produces),
                    "milestone_index": goal.milestone_index,
                }
                for gid, goal in self.backlog.goals.items()
            },
            "completed": list(self.backlog.completed),
            "in_progress": self.backlog.in_progress,
            "blocked": self.backlog.blocked,
            "external_refs": self._external_refs,  # RFC-049
            "active_epic": self.backlog.active_epic,  # RFC-115
            "active_milestone": self.backlog.active_milestone,  # RFC-115
        }

        # Use file locking for process safety (RFC-049/051)
        with open(current_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
