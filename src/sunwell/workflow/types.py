"""Workflow Types — Type definitions for autonomous execution (RFC-086)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal


class WorkflowTier(Enum):
    """Execution tiers for workflow chains."""

    FAST = "fast"  # Direct skill execution, no analysis
    LIGHT = "light"  # Brief acknowledgment, auto-proceed
    FULL = "full"  # Complete analysis, confirmation required


class IntentCategory(Enum):
    """Categories of user intent for routing."""

    CREATION = "creation"  # Write, create, document, draft, new
    VALIDATION = "validation"  # Check, audit, verify, validate
    TRANSFORMATION = "transformation"  # Restructure, split, modularize, fix
    REFINEMENT = "refinement"  # Improve, polish, enhance, tighten
    INFORMATION = "information"  # Help, what, how, explain


StepStatus = Literal["pending", "running", "success", "warning", "error", "skipped"]


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """A single step in a workflow chain."""

    skill: str
    """Skill reference: "validation/audit", "transformation/polish"."""

    purpose: str
    """Human-readable purpose of this step."""

    timeout_s: float = 60.0
    """Maximum execution time for this step."""

    interruptible: bool = True
    """Whether this step can be cancelled mid-execution."""


@dataclass(frozen=True, slots=True)
class WorkflowChain:
    """A pre-defined sequence of workflow steps."""

    name: str
    """Chain identifier: "feature-docs", "health-check"."""

    description: str
    """Human-readable description."""

    steps: tuple[WorkflowStep, ...]
    """Ordered sequence of steps."""

    checkpoint_after: tuple[int, ...] = ()
    """Step indices after which to pause for confirmation."""

    tier: WorkflowTier = WorkflowTier.LIGHT
    """Default execution tier."""


@dataclass(slots=True)
class WorkflowStepResult:
    """Result of executing a workflow step."""

    skill: str
    """Skill that was executed."""

    status: StepStatus
    """Execution status."""

    started_at: datetime
    """When execution started."""

    completed_at: datetime | None = None
    """When execution completed (None if still running)."""

    output: dict[str, Any] = field(default_factory=dict)
    """Step output data."""

    error: str | None = None
    """Error message if failed."""

    @property
    def duration_s(self) -> float | None:
        """Duration in seconds, or None if not completed."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "skill": self.skill,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output": self.output,
            "error": self.error,
        }


@dataclass(slots=True)
class WorkflowExecution:
    """State of an executing workflow."""

    id: str
    """Unique execution ID: "wf-2026-01-21-batch-api"."""

    chain: WorkflowChain
    """The workflow chain being executed."""

    current_step: int = 0
    """Index of current step (0-based)."""

    completed_steps: list[WorkflowStepResult] = field(default_factory=list)
    """Results of completed steps."""

    status: Literal["running", "paused", "completed", "error", "cancelled"] = "running"
    """Overall execution status."""

    started_at: datetime = field(default_factory=datetime.now)
    """When execution started."""

    updated_at: datetime = field(default_factory=datetime.now)
    """Last update timestamp."""

    context: dict[str, Any] = field(default_factory=dict)
    """Execution context (lens, target_file, etc.)."""

    @property
    def is_complete(self) -> bool:
        """Check if all steps are complete."""
        return self.current_step >= len(self.chain.steps)

    @property
    def progress_pct(self) -> float:
        """Progress as percentage (0-100)."""
        if not self.chain.steps:
            return 100.0
        return (self.current_step / len(self.chain.steps)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "id": self.id,
            "chain": self.chain.name,
            "current_step": self.current_step,
            "total_steps": len(self.chain.steps),
            "completed_steps": [s.to_dict() for s in self.completed_steps],
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "context": self.context,
        }


@dataclass(frozen=True, slots=True)
class Intent:
    """Classified user intent."""

    category: IntentCategory
    """Primary intent category."""

    confidence: float
    """Confidence score (0.0-1.0)."""

    signals: tuple[str, ...]
    """Keywords/phrases that triggered this classification."""

    suggested_workflow: str | None = None
    """Suggested workflow chain name."""

    tier: WorkflowTier = WorkflowTier.LIGHT
    """Recommended execution tier."""


# =============================================================================
# PRE-BUILT WORKFLOW CHAINS (RFC-086)
# =============================================================================

FEATURE_DOCS_CHAIN = WorkflowChain(
    name="feature-docs",
    description="Document a new feature end-to-end",
    steps=(
        WorkflowStep(skill="context-analyze", purpose="Understand feature scope, locate evidence"),
        WorkflowStep(skill="draft-claims", purpose="Extract verifiable claims from source code"),
        WorkflowStep(skill="write-structure", purpose="Structure content with Diataxis template"),
        WorkflowStep(skill="audit-enhanced", purpose="Validate all claims against code"),
        WorkflowStep(skill="apply-style", purpose="Apply style guide compliance"),
    ),
    checkpoint_after=(1, 3),  # Pause after draft and audit
    tier=WorkflowTier.FULL,
)

HEALTH_CHECK_CHAIN = WorkflowChain(
    name="health-check",
    description="Comprehensive validation of existing docs",
    steps=(
        WorkflowStep(skill="context-analyze", purpose="Understand document structure"),
        WorkflowStep(skill="audit-enhanced", purpose="Deep audit with confidence scoring"),
        WorkflowStep(skill="style-check", purpose="Check style guide compliance"),
        WorkflowStep(skill="code-example-audit", purpose="Verify code examples work"),
        WorkflowStep(skill="confidence-score", purpose="Calculate overall confidence"),
    ),
    checkpoint_after=(),  # Run all without pause
    tier=WorkflowTier.LIGHT,
)

QUICK_FIX_CHAIN = WorkflowChain(
    name="quick-fix",
    description="Fast issue resolution",
    steps=(
        WorkflowStep(skill="context-analyze", purpose="Understand the issue"),
        WorkflowStep(skill="auto-select-fixer", purpose="Choose appropriate fix strategy"),
        WorkflowStep(skill="audit", purpose="Verify the fix"),
    ),
    checkpoint_after=(),
    tier=WorkflowTier.FAST,
)

MODERNIZE_CHAIN = WorkflowChain(
    name="modernize",
    description="Update legacy documentation",
    steps=(
        WorkflowStep(skill="audit-enhanced", purpose="Assess current state"),
        WorkflowStep(skill="draft-updates", purpose="Draft necessary updates"),
        WorkflowStep(skill="modularize-content", purpose="Break into focused pages"),
        WorkflowStep(skill="apply-style", purpose="Apply modern style"),
        WorkflowStep(skill="reflexion-loop", purpose="Self-improve output"),
    ),
    checkpoint_after=(0, 3),
    tier=WorkflowTier.FULL,
)

# Registry of all pre-built chains
WORKFLOW_CHAINS: dict[str, WorkflowChain] = {
    "feature-docs": FEATURE_DOCS_CHAIN,
    "health-check": HEALTH_CHECK_CHAIN,
    "quick-fix": QUICK_FIX_CHAIN,
    "modernize": MODERNIZE_CHAIN,
}
