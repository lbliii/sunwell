"""Type definitions for Naaru Architecture (RFC-016, RFC-019, RFC-032, RFC-034).

The Naaru is Sunwell's coordinated intelligence architecture.

RFC-032 Additions:
- Task: Universal work unit (generalizes Opportunity)
- TaskMode: How tasks should be executed
- TaskStatus: Execution status of tasks
- TaskPlanner protocol: For task planning/decomposition

RFC-034 Additions:
- Contract-aware task fields (produces, requires, modifies)
- Parallel group support for concurrent execution
- Contract tracking for interface-first development

Note: RFC-067 types (TaskType, RequiredIntegration, IntegrationCheck, etc.)
have been moved to sunwell.integration.types for better organization.
"""


import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

# RFC-067 types - imported here for Task dataclass fields
from sunwell.integration.types import (
    IntegrationCheck,
    RequiredIntegration,
    TaskType,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# RFC-032: Task Types (Agent Mode)
# =============================================================================


class TaskMode(Enum):
    """How a task should be executed (RFC-032).

    This determines the execution strategy for a Task.
    """

    SELF_IMPROVE = "self_improve"  # Modify Sunwell's own code (RFC-019 behavior)
    GENERATE = "generate"          # Create new files/content
    MODIFY = "modify"              # Modify existing files
    EXECUTE = "execute"            # Run commands
    RESEARCH = "research"          # Gather information only (no side effects)
    COMPOSITE = "composite"        # Multi-step with subtasks


class TaskStatus(Enum):
    """Execution status of a task (RFC-032)."""

    PENDING = "pending"        # Not yet started
    READY = "ready"            # Dependencies satisfied, ready to execute
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"        # Waiting on dependencies
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"        # Skipped due to failed dependency


class SessionStatus(Enum):
    """Status of an autonomous session."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(Enum):
    """Risk level for proposals."""

    TRIVIAL = "trivial"    # Comments, docs, formatting
    LOW = "low"            # Additive changes, new patterns
    MEDIUM = "medium"      # Behavioral changes
    HIGH = "high"          # Structural changes, API changes
    CRITICAL = "critical"  # Core module changes

    def can_auto_apply(self) -> bool:
        """Check if this risk level allows auto-apply."""
        return self in [RiskLevel.TRIVIAL, RiskLevel.LOW]


class OpportunityCategory(Enum):
    """Categories of improvement opportunities."""

    ERROR_HANDLING = "error_handling"
    TESTING = "testing"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    OTHER = "other"


@dataclass
class Opportunity:
    """An identified improvement opportunity.

    Represents something Sunwell could improve about itself.
    """

    id: str
    category: OpportunityCategory
    description: str
    target_module: str
    priority: float  # 0.0 - 1.0, higher is more important
    estimated_effort: str  # trivial, small, medium, large
    risk_level: RiskLevel
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
            "target_module": self.target_module,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "risk_level": self.risk_level.value,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Opportunity:
        """Create from dict."""
        return cls(
            id=data["id"],
            category=OpportunityCategory(data["category"]),
            description=data["description"],
            target_module=data["target_module"],
            priority=data["priority"],
            estimated_effort=data["estimated_effort"],
            risk_level=RiskLevel(data["risk_level"]),
            details=data.get("details", {}),
        )

# =============================================================================
# RFC-032: Task (Universal Work Unit)
# RFC-034: Contract-Aware Parallel Task Planning
# =============================================================================
# NOTE: RFC-067 types moved to sunwell.integration.types


@dataclass
class Task:
    """A unit of work for Naaru to execute (RFC-032, RFC-034, RFC-067).

    Generalizes Opportunity to support any task type.
    The original Opportunity class remains unchanged for backward compatibility.
    Use Task.from_opportunity() and Task.to_opportunity() for conversion.

    Key additions over Opportunity:
    - mode: How to execute (generate, modify, execute, etc.)
    - tools: What tools this task may need
    - depends_on: Task dependencies for ordering
    - verification: How to verify completion
    - subtasks: For composite tasks

    RFC-034 additions:
    - produces: Artifacts this task creates (interfaces, types, files)
    - requires: Artifacts that must exist before this runs
    - modifies: Resources this task touches (for conflict detection)
    - parallel_group: Tasks in the same group can run concurrently
    - contract: Interface signature this task should conform to
    - is_contract: Whether this task defines an interface vs implements one

    RFC-067 additions:
    - task_type: Explicit categorization (create, wire, verify, refactor)
    - integrations: Structured wiring contracts for dependencies
    - verification_checks: Checks to run after task completion
    """

    id: str
    description: str
    mode: TaskMode

    # Execution context
    tools: frozenset[str] = field(default_factory=frozenset)  # Tools this task may use
    target_path: str | None = None       # File/directory to affect
    working_directory: str = "."

    # Dependencies
    depends_on: tuple[str, ...] = ()     # Task IDs that must complete first
    subtasks: tuple[Task, ...] = ()    # For composite tasks

    # === RFC-034: Contract-Aware Planning ===

    # Artifact flow (what this task produces/consumes)
    produces: frozenset[str] = field(default_factory=frozenset)
    """Artifacts this task creates: types, interfaces, files, modules.

    Example: frozenset(["UserProtocol", "user_types.py"])
    """

    requires: frozenset[str] = field(default_factory=frozenset)
    """Artifacts that must exist before this task can run.

    Unlike depends_on (task IDs), this is semantic: what artifacts are needed.
    Example: frozenset(["UserProtocol", "AuthInterface"])
    """

    modifies: frozenset[str] = field(default_factory=frozenset)
    """Resources this task may modify (for conflict detection).

    Two tasks with overlapping `modifies` sets cannot run in parallel.
    Example: frozenset(["src/models/user.py", "pyproject.toml"])
    """

    # Parallelization hints
    parallel_group: str | None = None
    """Tasks in the same parallel group can execute concurrently.

    Groups are typically phases: "contracts", "implementations", "tests".
    Tasks in the same group MUST have non-overlapping `modifies` sets.
    """

    # Contract information
    is_contract: bool = False
    """True if this task defines an interface/protocol, not an implementation.

    Contract tasks are inherently parallelizable (no shared mutable state).
    """

    contract: str | None = None
    """The interface signature this implementation should conform to.

    Example: "UserProtocol" - the implementation must satisfy this protocol.
    """

    # === RFC-067: Integration-Aware DAG ===

    task_type: TaskType = TaskType.CREATE
    """Explicit task categorization for DAG visualization.

    - CREATE: Creates new artifacts (default)
    - WIRE: Wires existing artifacts together
    - VERIFY: Verifies integrations are complete
    - REFACTOR: Restructures without changing behavior
    """

    integrations: tuple[RequiredIntegration, ...] = ()
    """How this task connects to its dependencies (not just what it needs).

    Makes the difference between:
    - requires: "I need UserProtocol to exist" (ordering)
    - integrations: "I must `from models.user import User`" (wiring)
    """

    verification_checks: tuple[IntegrationCheck, ...] = ()
    """Checks to run after task completion to verify integration.

    Wire tasks typically have verification_checks that ensure
    the wiring actually happened (import exists, call exists, etc.).
    """

    # Metadata (compatible with Opportunity)
    category: str = "general"
    priority: float = 0.5                # 0.0 - 1.0, higher is more important
    estimated_effort: str = "medium"     # trivial, small, medium, large
    risk_level: RiskLevel = RiskLevel.MEDIUM
    details: dict[str, Any] = field(default_factory=dict)

    # Execution state
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None

    # Verification
    verification: str | None = None           # How to verify completion
    verification_command: str | None = None   # Command to run for verification

    def is_ready(
        self,
        completed_ids: set[str],
        completed_artifacts: set[str] | None = None,
    ) -> bool:
        """Check if all dependencies are satisfied (RFC-034, RFC-067 enhanced).

        Args:
            completed_ids: Set of completed task IDs
            completed_artifacts: Set of produced artifacts (RFC-034)

        Returns:
            True if both task dependencies AND required artifacts are satisfied
        """
        # Check task dependencies
        if not all(dep in completed_ids for dep in self.depends_on):
            return False

        # RFC-034: Check artifact requirements
        if completed_artifacts is not None and self.requires:
            if not self.requires <= completed_artifacts:
                return False

        return True

    def is_wire_task(self) -> bool:
        """Check if this is an integration wiring task (RFC-067).

        Wire tasks are explicit tasks that connect artifacts together.
        They cannot be skipped and have verification checks.
        """
        return self.task_type == TaskType.WIRE

    def is_verify_task(self) -> bool:
        """Check if this is a verification task (RFC-067).

        Verify tasks check that all integrations are complete.
        """
        return self.task_type == TaskType.VERIFY

    def has_pending_verifications(self) -> bool:
        """Check if this task has verification checks that need to run (RFC-067)."""
        return len(self.verification_checks) > 0

    def to_opportunity(self) -> Opportunity:
        """Convert to legacy Opportunity type for backward compatibility.

        Use this when interfacing with code that expects the original
        Opportunity type from RFC-019.
        """
        # Map category string to OpportunityCategory
        try:
            category = OpportunityCategory(self.category)
        except ValueError:
            category = OpportunityCategory.OTHER

        return Opportunity(
            id=self.id,
            category=category,
            description=self.description,
            target_module=self.target_path or "",
            priority=self.priority,
            estimated_effort=self.estimated_effort,
            risk_level=self.risk_level,
            details=self.details,
        )

    @classmethod
    def from_opportunity(cls, opp: Opportunity) -> Task:
        """Create Task from legacy Opportunity.

        Use this to upgrade existing Opportunity objects to Tasks.
        """
        return cls(
            id=opp.id,
            description=opp.description,
            mode=TaskMode.SELF_IMPROVE,
            target_path=opp.target_module,
            category=opp.category.value if hasattr(opp.category, "value") else str(opp.category),
            priority=opp.priority,
            estimated_effort=opp.estimated_effort,
            risk_level=opp.risk_level,
            details=opp.details,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "description": self.description,
            "mode": self.mode.value,
            "tools": list(self.tools),
            "target_path": self.target_path,
            "working_directory": self.working_directory,
            "depends_on": list(self.depends_on),
            "subtasks": [s.to_dict() for s in self.subtasks],
            # RFC-034: Contract-aware fields
            "produces": list(self.produces),
            "requires": list(self.requires),
            "modifies": list(self.modifies),
            "parallel_group": self.parallel_group,
            "is_contract": self.is_contract,
            "contract": self.contract,
            # RFC-067: Integration-aware fields
            "task_type": self.task_type.value,
            "integrations": [i.to_dict() for i in self.integrations],
            "verification_checks": [c.to_dict() for c in self.verification_checks],
            # Metadata
            "category": self.category,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "risk_level": self.risk_level.value,
            "details": self.details,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "verification": self.verification,
            "verification_command": self.verification_command,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create from dict."""
        subtasks = tuple(
            cls.from_dict(s) for s in data.get("subtasks", [])
        )
        # RFC-067: Parse integrations and verification checks
        integrations = tuple(
            RequiredIntegration.from_dict(i) for i in data.get("integrations", [])
        )
        verification_checks = tuple(
            IntegrationCheck.from_dict(c) for c in data.get("verification_checks", [])
        )
        return cls(
            id=data["id"],
            description=data["description"],
            mode=TaskMode(data.get("mode", "generate")),
            tools=frozenset(data.get("tools", [])),
            target_path=data.get("target_path"),
            working_directory=data.get("working_directory", "."),
            depends_on=tuple(data.get("depends_on", [])),
            subtasks=subtasks,
            # RFC-034: Contract-aware fields
            produces=frozenset(data.get("produces", [])),
            requires=frozenset(data.get("requires", [])),
            modifies=frozenset(data.get("modifies", [])),
            parallel_group=data.get("parallel_group"),
            is_contract=data.get("is_contract", False),
            contract=data.get("contract"),
            # RFC-067: Integration-aware fields
            task_type=TaskType(data.get("task_type", "create")),
            integrations=integrations,
            verification_checks=verification_checks,
            # Metadata
            category=data.get("category", "general"),
            priority=data.get("priority", 0.5),
            estimated_effort=data.get("estimated_effort", "medium"),
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            details=data.get("details", {}),
            status=TaskStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            verification=data.get("verification"),
            verification_command=data.get("verification_command"),
        )


@dataclass
class SessionConfig:
    """Configuration for an autonomous session.

    Controls how long the session runs, what it can do automatically,
    and various safety limits.
    """

    goals: list[str]
    max_hours: float = 8.0
    max_proposals: int = 50
    max_auto_apply: int = 10
    auto_apply_enabled: bool = True
    checkpoint_interval_minutes: int = 15
    min_seconds_between_changes: int = 30
    max_consecutive_failures: int = 3
    verbose: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "goals": self.goals,
            "max_hours": self.max_hours,
            "max_proposals": self.max_proposals,
            "max_auto_apply": self.max_auto_apply,
            "auto_apply_enabled": self.auto_apply_enabled,
            "checkpoint_interval_minutes": self.checkpoint_interval_minutes,
            "min_seconds_between_changes": self.min_seconds_between_changes,
            "max_consecutive_failures": self.max_consecutive_failures,
            "verbose": self.verbose,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionConfig:
        """Create from dict."""
        return cls(**data)


@dataclass
class CompletedTask:
    """Record of a completed task."""

    opportunity_id: str
    proposal_id: str | None
    result: str  # auto_applied, queued, rejected, failed
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "opportunity_id": self.opportunity_id,
            "proposal_id": self.proposal_id,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class SessionState:
    """Persistent state for an autonomous session.

    This is saved to disk at checkpoints and can be used
    to resume a paused session.
    """

    session_id: str
    config: SessionConfig
    status: SessionStatus = SessionStatus.INITIALIZING
    started_at: datetime = field(default_factory=datetime.now)
    checkpoint_at: datetime | None = None
    stopped_at: datetime | None = None
    stop_reason: str | None = None

    # Progress tracking
    opportunities: list[Opportunity] = field(default_factory=list)
    completed: list[CompletedTask] = field(default_factory=list)
    current_task: Opportunity | None = None

    # Counters
    proposals_created: int = 0
    proposals_auto_applied: int = 0
    proposals_queued: int = 0
    proposals_rejected: int = 0
    consecutive_failures: int = 0

    # Timing
    total_runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "checkpoint_at": self.checkpoint_at.isoformat() if self.checkpoint_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "stop_reason": self.stop_reason,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "completed": [c.to_dict() for c in self.completed],
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "proposals_created": self.proposals_created,
            "proposals_auto_applied": self.proposals_auto_applied,
            "proposals_queued": self.proposals_queued,
            "proposals_rejected": self.proposals_rejected,
            "consecutive_failures": self.consecutive_failures,
            "total_runtime_seconds": self.total_runtime_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dict."""
        state = cls(
            session_id=data["session_id"],
            config=SessionConfig.from_dict(data["config"]),
            status=SessionStatus(data["status"]),
            started_at=datetime.fromisoformat(data["started_at"]),
        )

        if data.get("checkpoint_at"):
            state.checkpoint_at = datetime.fromisoformat(data["checkpoint_at"])
        if data.get("stopped_at"):
            state.stopped_at = datetime.fromisoformat(data["stopped_at"])

        state.stop_reason = data.get("stop_reason")
        state.opportunities = [Opportunity.from_dict(o) for o in data.get("opportunities", [])]
        state.current_task = (
            Opportunity.from_dict(data["current_task"])
            if data.get("current_task") else None
        )

        state.proposals_created = data.get("proposals_created", 0)
        state.proposals_auto_applied = data.get("proposals_auto_applied", 0)
        state.proposals_queued = data.get("proposals_queued", 0)
        state.proposals_rejected = data.get("proposals_rejected", 0)
        state.consecutive_failures = data.get("consecutive_failures", 0)
        state.total_runtime_seconds = data.get("total_runtime_seconds", 0.0)

        return state

    def save(self, path: Path) -> None:
        """Save state to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> SessionState:
        """Load state from file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def get_progress_summary(self) -> dict[str, Any]:
        """Get a summary of current progress."""
        total_opportunities = len(self.opportunities) + len(self.completed)
        completed_count = len(self.completed)

        return {
            "opportunities_total": total_opportunities,
            "opportunities_completed": completed_count,
            "opportunities_remaining": len(self.opportunities),
            "proposals_created": self.proposals_created,
            "proposals_auto_applied": self.proposals_auto_applied,
            "proposals_queued": self.proposals_queued,
            "proposals_rejected": self.proposals_rejected,
            "success_rate": (
                completed_count / total_opportunities
                if total_opportunities > 0 else 0
            ),
        }
