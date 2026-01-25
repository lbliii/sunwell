"""Goal Generation for Autonomous Backlog (RFC-046 Phase 2).

Convert signals into prioritized goals with dependency inference.
"""


import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sunwell.features.backlog.signals import ObservableSignal

if TYPE_CHECKING:
    from sunwell.knowledge.codebase.context import ProjectContext

# Priority weights for goal categories (module-level constants for performance)
_CATEGORY_WEIGHTS: dict[str, float] = {
    "security": 1.0,
    "fix": 0.9,
    "performance": 0.8,
    "test": 0.7,
    "add": 0.6,
    "improve": 0.5,
    "refactor": 0.4,
    "document": 0.3,
}

# Complexity weights (quick wins first)
_COMPLEXITY_WEIGHTS: dict[str, float] = {
    "trivial": 1.0,
    "simple": 0.9,
    "moderate": 0.7,
    "complex": 0.5,
}


@dataclass(frozen=True, slots=True)
class GoalResult:
    """Result of goal execution."""

    success: bool
    """Whether goal completed successfully."""

    failure_reason: str = ""
    """Reason if failed."""

    summary: str = ""
    """Human-readable summary of execution."""

    duration_seconds: float = 0.0
    """Time taken to complete."""

    files_changed: tuple[str, ...] = ()
    """Files that were modified."""

    artifacts_created: tuple[str, ...] = ()
    """Artifact IDs that were created (RFC-094)."""


@dataclass(frozen=True, slots=True)
class GoalScope:
    """Bounded scope to prevent unbounded changes."""

    max_files: int = 5
    """Maximum files this goal should touch."""

    max_lines_changed: int = 500
    """Maximum lines added/removed."""

    allowed_paths: frozenset[Path] = frozenset()
    """If set, restrict changes to these paths."""

    forbidden_paths: frozenset[Path] = frozenset()
    """Never touch these paths."""


@dataclass(frozen=True, slots=True)
class Goal:
    """A generated goal ready for execution."""

    id: str
    title: str
    description: str

    source_signals: tuple[str, ...]
    """IDs of signals that generated this goal."""

    priority: float
    """0-1, higher = more urgent."""

    estimated_complexity: Literal["trivial", "simple", "moderate", "complex"]

    requires: frozenset[str]
    """Goal IDs this depends on."""

    category: Literal[
        "fix",  # Something broken
        "improve",  # Something suboptimal
        "add",  # Something missing
        "refactor",  # Structural improvement
        "document",  # Documentation gap
        "test",  # Test coverage
        "security",  # Security-related
        "performance",  # Performance-related
    ]

    auto_approvable: bool
    """Can this be executed without human approval?"""

    scope: GoalScope
    """Bounded scope for safety."""

    external_ref: str | None = None
    """External reference for deduplication (e.g., 'github:issue:123').

    Using string ref instead of ExternalEvent object because:
    1. Goal is frozen/serialized — embedding mutable event data is problematic
    2. Deduplication only needs the ref, not full event
    3. Full event can be stored separately in ExternalEventStore
    """

    # RFC-051: Multi-instance coordination fields
    claimed_by: int | None = None
    """Worker ID that claimed this goal (None = unclaimed)."""

    claimed_at: datetime | None = None
    """When the goal was claimed."""

    # RFC-067: Integration-Aware DAG fields
    produces: tuple[str, ...] = ()
    """Artifact IDs this goal produces (e.g., 'UserModel', 'login_route').

    Artifacts are explicit outputs that can be verified and connected.
    """

    integrations: tuple[str, ...] = ()
    """Integration requirements as serialized JSON strings.

    Each string is a JSON-encoded RequiredIntegration that specifies
    how this goal connects to its dependencies (import, call, route, etc.).
    Use Goal.get_integrations() to deserialize.
    """

    verification_checks: tuple[str, ...] = ()
    """Verification checks as serialized JSON strings.

    Each string is a JSON-encoded IntegrationCheck to run after completion.
    Use Goal.get_verification_checks() to deserialize.
    """

    task_type: Literal["create", "wire", "verify", "refactor"] = "create"
    """RFC-067: What kind of task this is.

    - create: Generate new artifacts
    - wire: Connect artifacts together (import, register, call)
    - verify: Check integrations work end-to-end
    - refactor: Restructure without changing behavior
    """

    # RFC-115: Hierarchical Goal Decomposition fields
    goal_type: Literal["epic", "milestone", "task"] = "task"
    """What level of the hierarchy this goal represents.

    - epic: Ambitious multi-phase goal (e.g., "build an RTS game")
    - milestone: A coherent phase within an epic
    - task: Concrete work item (default, HarmonicPlanner output)
    """

    parent_goal_id: str | None = None
    """Epic or milestone this belongs to (None for top-level epics/tasks)."""

    milestone_produces: tuple[str, ...] = ()
    """High-level artifacts this milestone will create.

    Used for dependency inference between milestones before detailed planning.
    E.g., ("Window", "Renderer", "Input", "GameState")
    """

    milestone_index: int | None = None
    """Order within parent epic (0-indexed). None for epics and tasks."""

    def is_wire_task(self) -> bool:
        """Check if this is a wiring task (RFC-067)."""
        return self.task_type == "wire"

    def is_verify_task(self) -> bool:
        """Check if this is a verification task (RFC-067)."""
        return self.task_type == "verify"

    def is_epic(self) -> bool:
        """Check if this is an epic (RFC-115)."""
        return self.goal_type == "epic"

    def is_milestone(self) -> bool:
        """Check if this is a milestone (RFC-115)."""
        return self.goal_type == "milestone"

    def is_task(self) -> bool:
        """Check if this is a regular task (RFC-115)."""
        return self.goal_type == "task"


@dataclass(frozen=True, slots=True)
class GoalPolicy:
    """Policy for goal generation."""

    max_goals: int = 20
    """Maximum goals in backlog."""

    priority_threshold: float = 0.2
    """Drop goals below this priority."""

    auto_approve_categories: frozenset[str] = frozenset({"fix", "test"})
    """Categories that can be auto-approved."""

    auto_approve_complexity: frozenset[str] = frozenset({"trivial", "simple"})
    """Complexity levels that can be auto-approved."""

    exclude_paths: frozenset[Path] = frozenset()
    """Paths to exclude from goal generation."""


class GoalGenerator:
    """Generate and prioritize goals from signals."""

    def __init__(
        self,
        context: ProjectContext | None = None,
        policy: GoalPolicy | None = None,
    ):
        """Initialize goal generator.

        Args:
            context: Optional project context (for intelligence signals)
            policy: Goal generation policy
        """
        self.context = context
        self.policy = policy or GoalPolicy()

    async def generate(
        self,
        observable_signals: list[ObservableSignal],
        intelligence_signals: list = None,  # Future: IntelligenceSignal
        explicit_goals: list[str] | None = None,
    ) -> list[Goal]:
        """Generate prioritized goal list.

        Args:
            observable_signals: Signals from code analysis
            intelligence_signals: Signals from project intelligence (optional)
            explicit_goals: User-provided goals

        Returns:
            Prioritized list of goals
        """
        # 1. Convert signals to candidate goals
        candidates: list[Goal] = []
        candidates.extend(self._goals_from_observable(observable_signals))
        # Future: candidates.extend(self._goals_from_intelligence(intelligence_signals))
        if explicit_goals:
            candidates.extend(self._goals_from_explicit(explicit_goals))

        # 2. Deduplicate (same root cause = one goal)
        deduplicated = self._deduplicate_goals(candidates)

        # 3. Build dependency graph
        with_deps = await self._infer_dependencies(deduplicated)

        # 4. Score and prioritize
        prioritized = self._prioritize(with_deps)

        # 5. Apply policy limits
        filtered = self._apply_policy(prioritized)

        return filtered

    def _goals_from_observable(
        self,
        signals: list[ObservableSignal],
    ) -> list[Goal]:
        """Convert observable signals to goals."""
        goals: list[Goal] = []

        for signal in signals:
            signal_id = self._signal_id(signal)

            if signal.signal_type == "failing_test":
                goals.append(
                    Goal(
                        id=f"fix-test-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}",
                        title=f"Fix failing test: {signal.location.symbol or 'unknown'}",
                        description=signal.message,
                        source_signals=(signal_id,),
                        priority=0.95 if signal.severity == "critical" else 0.8,
                        estimated_complexity="simple",
                        requires=frozenset(),
                        category="fix",
                        auto_approvable=True,  # Tests are safe to fix
                        scope=GoalScope(max_files=2, max_lines_changed=100),
                    )
                )

            elif signal.signal_type in ("todo_comment", "fixme_comment"):
                goals.append(
                    Goal(
                        id=f"todo-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}",
                        title=f"Address {signal.signal_type.replace('_', ' ').title()}: {signal.message[:50]}",
                        description=signal.message,
                        source_signals=(signal_id,),
                        priority=0.4 if signal.signal_type == "fixme_comment" else 0.3,
                        estimated_complexity="moderate",
                        requires=frozenset(),
                        category="improve",
                        auto_approvable=False,  # TODOs need human judgment
                        scope=GoalScope(max_files=3, max_lines_changed=200),
                    )
                )

            elif signal.signal_type == "type_error":
                goals.append(
                    Goal(
                        id=f"type-error-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}",
                        title=f"Fix type error in {signal.location.file.name}",
                        description=signal.message,
                        source_signals=(signal_id,),
                        priority=0.85,
                        estimated_complexity="moderate",
                        requires=frozenset(),
                        category="fix",
                        auto_approvable=False,  # Type errors need careful fixing
                        scope=GoalScope(max_files=2, max_lines_changed=150),
                    )
                )

            elif signal.signal_type == "lint_warning":
                if signal.auto_fixable:
                    goals.append(
                        Goal(
                            id=f"lint-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}",
                            title=f"Fix lint warning in {signal.location.file.name}",
                            description=signal.message,
                            source_signals=(signal_id,),
                            priority=0.5,
                            estimated_complexity="trivial",
                            requires=frozenset(),
                            category="fix",
                            auto_approvable=True,  # Auto-fixable lint
                            scope=GoalScope(max_files=1, max_lines_changed=50),
                        )
                    )

            elif signal.signal_type == "missing_test":
                goals.append(
                    Goal(
                        id=f"coverage-{hashlib.blake2b(signal_id.encode(), digest_size=4).hexdigest()}",
                        title=f"Add test coverage for {signal.location.file.name}",
                        description=signal.message,
                        source_signals=(signal_id,),
                        priority=0.6,
                        estimated_complexity="moderate",
                        requires=frozenset(),
                        category="test",
                        auto_approvable=False,  # Test writing needs judgment
                        scope=GoalScope(max_files=2, max_lines_changed=300),
                    )
                )

        return goals

    def _goals_from_explicit(self, explicit_goals: list[str]) -> list[Goal]:
        """Convert explicit user goals to Goal objects."""
        goals: list[Goal] = []

        for i, goal_text in enumerate(explicit_goals):
            goals.append(
                Goal(
                    id=f"explicit-{i}",
                    title=goal_text[:60],
                    description=goal_text,
                    source_signals=(),
                    priority=0.9,  # High priority for explicit requests
                    estimated_complexity="moderate",
                    requires=frozenset(),
                    category="add",
                    auto_approvable=False,  # Explicit goals need approval
                    scope=GoalScope(max_files=10, max_lines_changed=1000),
                )
            )

        return goals

    def _signal_id(self, signal: ObservableSignal) -> str:
        """Generate unique ID for a signal."""
        return f"{signal.signal_type}:{signal.location.file}:{signal.location.line_start}"

    def _deduplicate_goals(self, goals: list[Goal]) -> list[Goal]:
        """Deduplicate goals with same root cause."""
        # Group by file and category
        grouped: dict[tuple[Path, str], list[Goal]] = {}

        for goal in goals:
            # Extract file from first source signal if available
            file_path = Path(".")
            if goal.source_signals:
                # Parse signal ID: "type:file:line"
                parts = goal.source_signals[0].split(":")
                if len(parts) >= 2:
                    file_path = Path(parts[1])

            key = (file_path, goal.category)
            grouped.setdefault(key, []).append(goal)

        # Keep highest priority goal from each group
        deduplicated: list[Goal] = []
        for group_goals in grouped.values():
            if len(group_goals) == 1:
                deduplicated.append(group_goals[0])
            else:
                # Merge: take highest priority, combine signals
                best = max(group_goals, key=lambda g: g.priority)
                # Combine all source signals
                all_signals = tuple(
                    sig for g in group_goals for sig in g.source_signals
                )
                deduplicated.append(
                    Goal(
                        id=best.id,
                        title=best.title,
                        description=best.description,
                        source_signals=all_signals,
                        priority=best.priority,
                        estimated_complexity=best.estimated_complexity,
                        requires=best.requires,
                        category=best.category,
                        auto_approvable=best.auto_approvable,
                        scope=best.scope,
                    )
                )

        return deduplicated

    async def _infer_dependencies(self, goals: list[Goal]) -> list[Goal]:
        """Infer dependencies between goals.

        Rules:
        - Fix tests before refactoring
        - Fix type errors before adding features
        - Fix lint before other changes
        """
        updated: list[Goal] = []

        for goal in goals:
            requires = set(goal.requires)

            # Fix tests before refactoring
            if goal.category == "refactor":
                for other in goals:
                    if other.category == "fix" and "test" in other.title.lower():
                        requires.add(other.id)

            # Fix type errors before adding features
            if goal.category == "add":
                for other in goals:
                    if other.category == "fix" and "type" in other.title.lower():
                        requires.add(other.id)

            # Fix lint before other changes
            if goal.category in ("add", "refactor", "improve"):
                for other in goals:
                    if other.category == "fix" and "lint" in other.title.lower():
                        requires.add(other.id)

            updated.append(
                Goal(
                    id=goal.id,
                    title=goal.title,
                    description=goal.description,
                    source_signals=goal.source_signals,
                    priority=goal.priority,
                    estimated_complexity=goal.estimated_complexity,
                    requires=frozenset(requires),
                    category=goal.category,
                    auto_approvable=goal.auto_approvable,
                    scope=goal.scope,
                )
            )

        return updated

    def _prioritize(self, goals: list[Goal]) -> list[Goal]:
        """Score goals by priority.

        Priority factors:
        - Category: security > fix > test > improve > refactor > document
        - Severity: critical > high > medium > low
        - Complexity: trivial > simple > moderate > complex (quick wins first)
        - Dependencies: leaves before roots (unblock others)
        """
        # Calculate adjusted priority and create new goals with updated priority
        prioritized_goals = []
        for goal in goals:
            category_weight = _CATEGORY_WEIGHTS.get(goal.category, 0.5)
            complexity_weight = _COMPLEXITY_WEIGHTS.get(
                goal.estimated_complexity, 0.7
            )

            # Boost leaves (no dependencies)
            dependency_boost = 0.1 if not goal.requires else 0.0

            adjusted = (
                goal.priority * category_weight * complexity_weight + dependency_boost
            )
            # Clamp to [0, 1]
            adjusted = min(1.0, max(0.0, adjusted))

            # Create new goal with adjusted priority
            prioritized_goals.append(
                Goal(
                    id=goal.id,
                    title=goal.title,
                    description=goal.description,
                    source_signals=goal.source_signals,
                    priority=adjusted,
                    estimated_complexity=goal.estimated_complexity,
                    requires=goal.requires,
                    category=goal.category,
                    auto_approvable=goal.auto_approvable,
                    scope=goal.scope,
                )
            )

        # Sort by adjusted priority (highest first)
        return sorted(prioritized_goals, key=lambda g: g.priority, reverse=True)

    def _apply_policy(self, goals: list[Goal]) -> list[Goal]:
        """Apply policy limits to goals."""
        filtered = [
            g
            for g in goals
            if g.priority >= self.policy.priority_threshold
            and not any(
                str(g.source_signals[0]).startswith(str(exclude))
                if g.source_signals
                else False
                for exclude in self.policy.exclude_paths
            )
        ]

        # Limit count
        return filtered[: self.policy.max_goals]
