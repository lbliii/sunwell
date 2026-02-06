"""Structured Handoff Protocol for self-driving agent coordination.

Handoffs propagate knowledge upward from workers/subplanners to parent
planners. Unlike TaskResult (which is outcome-focused), Handoff captures
what was LEARNED -- findings, concerns, deviations, and suggestions.

This enables dynamic replanning: parent planners receive handoffs as
follow-up context, enabling them to adjust strategy based on what
workers discovered during execution.

Inspired by: "The handoff contains not just what was done, but important
notes, concerns, deviations, findings, thoughts, and feedback."
(Cursor self-driving codebases research, Feb 2026)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.coordination.parallel_executor import TaskResult


class HandoffUrgency(Enum):
    """Urgency of a handoff concern or finding."""

    LOW = "low"
    """Informational -- planner can act on it when convenient."""

    MEDIUM = "medium"
    """Worth considering before next planning cycle."""

    HIGH = "high"
    """Should influence immediate replanning decisions."""

    CRITICAL = "critical"
    """Blocks further progress -- planner must address."""


@dataclass(frozen=True, slots=True)
class Finding:
    """Something discovered during execution.

    Findings are knowledge that the planner didn't have when it
    created the task. They enable the system to converge by
    propagating information upward.
    """

    description: str
    """What was discovered."""

    category: str = "general"
    """Category: 'architecture', 'dependency', 'pattern', 'risk', 'opportunity'."""

    urgency: HandoffUrgency = HandoffUrgency.LOW
    """How urgently the planner should act on this."""

    affected_files: tuple[str, ...] = ()
    """Files related to this finding."""


@dataclass(frozen=True, slots=True)
class Deviation:
    """Where the worker diverged from the plan.

    Deviations are not failures -- they represent informed decisions
    the worker made based on ground truth that the planner didn't have.
    """

    original_plan: str
    """What the planner asked for."""

    actual_approach: str
    """What the worker actually did."""

    reason: str
    """Why the worker diverged."""


@dataclass(frozen=True, slots=True)
class Handoff:
    """Structured knowledge transfer from worker/subplanner to parent planner.

    Handoffs are the communication primitive that enables self-driving
    convergence. Workers produce handoffs on completion; parent planners
    consume them to make informed replanning decisions.

    The key insight is that handoffs carry MORE than just success/failure:
    they carry the knowledge the worker gained during execution, enabling
    the system to converge toward a solution even when individual tasks
    encounter unexpected situations.

    Usage:
        # Worker creates handoff after completing a task
        handoff = Handoff.from_task_result(
            task_id="impl-auth",
            result=task_result,
            findings=(Finding("OAuth requires PKCE for SPA clients"),),
            concerns=("Rate limiting not implemented yet",),
            suggestions=("Add token refresh middleware",),
        )

        # Parent planner receives handoff and adjusts strategy
        planner.receive_handoff(handoff)
    """

    task_id: str
    """ID of the task this handoff is for."""

    worker_id: str
    """ID of the worker/subplanner that produced this."""

    # === Outcome ===
    success: bool
    """Whether the task completed successfully."""

    summary: str
    """Brief summary of what was accomplished."""

    artifacts: tuple[str, ...] = ()
    """Paths of artifacts created or modified."""

    duration_ms: int = 0
    """Execution time in milliseconds."""

    error: str | None = None
    """Error message if task failed."""

    # === Knowledge (the key differentiator from TaskResult) ===
    findings: tuple[Finding, ...] = ()
    """Things discovered during execution that the planner should know."""

    concerns: tuple[str, ...] = ()
    """Risks or issues worth flagging to the planner."""

    deviations: tuple[Deviation, ...] = ()
    """Where the worker diverged from the original plan."""

    suggestions: tuple[str, ...] = ()
    """Ideas for follow-up work the planner should consider."""

    # === Context ===
    context_snapshot: str = ""
    """Brief summary of execution context for the planner."""

    files_examined: tuple[str, ...] = ()
    """Files the worker read (not just modified) -- useful for understanding scope."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When this handoff was created."""

    @classmethod
    def from_task_result(
        cls,
        task_id: str,
        result: TaskResult,
        worker_id: str = "",
        findings: tuple[Finding, ...] = (),
        concerns: tuple[str, ...] = (),
        deviations: tuple[Deviation, ...] = (),
        suggestions: tuple[str, ...] = (),
        context_snapshot: str = "",
        files_examined: tuple[str, ...] = (),
    ) -> Handoff:
        """Create a Handoff from a TaskResult with additional knowledge.

        This is the primary factory method. Workers call this after completing
        a task, enriching the bare TaskResult with learned knowledge.

        Args:
            task_id: ID of the completed task
            result: The task execution result
            worker_id: ID of the worker that produced this
            findings: Things discovered during execution
            concerns: Risks or issues to flag
            deviations: Where the worker diverged from the plan
            suggestions: Ideas for follow-up work
            context_snapshot: Brief execution context summary
            files_examined: Files the worker read

        Returns:
            Handoff with combined outcome and knowledge
        """
        return cls(
            task_id=task_id,
            worker_id=worker_id or f"worker-{task_id}",
            success=result.success,
            summary=result.output or ("Completed successfully" if result.success else "Failed"),
            artifacts=tuple(result.artifacts),
            duration_ms=result.duration_ms,
            error=result.error,
            findings=findings,
            concerns=concerns,
            deviations=deviations,
            suggestions=suggestions,
            context_snapshot=context_snapshot,
            files_examined=files_examined,
        )

    @classmethod
    def failure(
        cls,
        task_id: str,
        error: str,
        worker_id: str = "",
        findings: tuple[Finding, ...] = (),
        concerns: tuple[str, ...] = (),
        context_snapshot: str = "",
    ) -> Handoff:
        """Create a failure Handoff.

        Even failed tasks can produce valuable findings -- e.g., discovering
        that a dependency doesn't exist or an API has changed.

        Args:
            task_id: ID of the failed task
            error: Error description
            worker_id: ID of the worker
            findings: Things discovered despite the failure
            concerns: Risks to flag
            context_snapshot: Brief execution context

        Returns:
            Handoff marking failure with captured knowledge
        """
        return cls(
            task_id=task_id,
            worker_id=worker_id or f"worker-{task_id}",
            success=False,
            summary=f"Failed: {error}",
            error=error,
            findings=findings,
            concerns=concerns,
            context_snapshot=context_snapshot,
        )

    def to_planner_context(self) -> str:
        """Format handoff as context for the parent planner.

        This is injected into the planner's conversation as a follow-up
        message, enabling dynamic replanning.

        Returns:
            Formatted string suitable for injection into planner context
        """
        lines = [
            f"## Handoff from {self.worker_id}",
            "",
            f"**Task**: {self.task_id}",
            f"**Status**: {'Completed' if self.success else 'Failed'}",
            f"**Summary**: {self.summary}",
        ]

        if self.error:
            lines.append(f"**Error**: {self.error}")

        if self.artifacts:
            lines.append(f"**Artifacts**: {', '.join(self.artifacts)}")

        if self.findings:
            lines.append("")
            lines.append("### Findings")
            for f in self.findings:
                urgency_marker = ""
                if f.urgency in (HandoffUrgency.HIGH, HandoffUrgency.CRITICAL):
                    urgency_marker = f" [{f.urgency.value.upper()}]"
                lines.append(f"- {f.description}{urgency_marker}")
                if f.affected_files:
                    lines.append(f"  Files: {', '.join(f.affected_files)}")

        if self.concerns:
            lines.append("")
            lines.append("### Concerns")
            for c in self.concerns:
                lines.append(f"- {c}")

        if self.deviations:
            lines.append("")
            lines.append("### Deviations from Plan")
            for d in self.deviations:
                lines.append(f"- **Planned**: {d.original_plan}")
                lines.append(f"  **Actual**: {d.actual_approach}")
                lines.append(f"  **Reason**: {d.reason}")

        if self.suggestions:
            lines.append("")
            lines.append("### Suggestions")
            for s in self.suggestions:
                lines.append(f"- {s}")

        if self.context_snapshot:
            lines.append("")
            lines.append(f"### Context")
            lines.append(self.context_snapshot)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage/transmission."""
        return {
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "success": self.success,
            "summary": self.summary,
            "artifacts": list(self.artifacts),
            "duration_ms": self.duration_ms,
            "error": self.error,
            "findings": [
                {
                    "description": f.description,
                    "category": f.category,
                    "urgency": f.urgency.value,
                    "affected_files": list(f.affected_files),
                }
                for f in self.findings
            ],
            "concerns": list(self.concerns),
            "deviations": [
                {
                    "original_plan": d.original_plan,
                    "actual_approach": d.actual_approach,
                    "reason": d.reason,
                }
                for d in self.deviations
            ],
            "suggestions": list(self.suggestions),
            "context_snapshot": self.context_snapshot,
            "files_examined": list(self.files_examined),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Handoff:
        """Deserialize from dict."""
        findings = tuple(
            Finding(
                description=f["description"],
                category=f.get("category", "general"),
                urgency=HandoffUrgency(f.get("urgency", "low")),
                affected_files=tuple(f.get("affected_files", [])),
            )
            for f in data.get("findings", [])
        )

        deviations = tuple(
            Deviation(
                original_plan=d["original_plan"],
                actual_approach=d["actual_approach"],
                reason=d["reason"],
            )
            for d in data.get("deviations", [])
        )

        timestamp = datetime.now()
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            task_id=data["task_id"],
            worker_id=data.get("worker_id", ""),
            success=data["success"],
            summary=data.get("summary", ""),
            artifacts=tuple(data.get("artifacts", [])),
            duration_ms=data.get("duration_ms", 0),
            error=data.get("error"),
            findings=findings,
            concerns=tuple(data.get("concerns", [])),
            deviations=deviations,
            suggestions=tuple(data.get("suggestions", [])),
            context_snapshot=data.get("context_snapshot", ""),
            files_examined=tuple(data.get("files_examined", [])),
            timestamp=timestamp,
        )


@dataclass(slots=True)
class HandoffCollector:
    """Collects handoffs from multiple workers for a parent planner.

    Aggregates knowledge across all handoffs and provides a combined
    view for the planner to use in replanning decisions.

    Usage:
        collector = HandoffCollector()
        collector.add(handoff_from_worker_1)
        collector.add(handoff_from_worker_2)

        # Get combined context for planner
        context = collector.to_planner_context()

        # Check if any critical concerns
        if collector.has_critical_concerns():
            planner.replan()
    """

    handoffs: list[Handoff] = field(default_factory=list)
    """Collected handoffs in order received."""

    def add(self, handoff: Handoff) -> None:
        """Add a handoff to the collector."""
        self.handoffs.append(handoff)

    @property
    def all_success(self) -> bool:
        """True if all collected handoffs report success."""
        return all(h.success for h in self.handoffs)

    @property
    def success_count(self) -> int:
        """Number of successful handoffs."""
        return sum(1 for h in self.handoffs if h.success)

    @property
    def failure_count(self) -> int:
        """Number of failed handoffs."""
        return sum(1 for h in self.handoffs if not h.success)

    @property
    def all_findings(self) -> list[Finding]:
        """All findings across all handoffs, sorted by urgency."""
        findings = [f for h in self.handoffs for f in h.findings]
        urgency_order = {
            HandoffUrgency.CRITICAL: 0,
            HandoffUrgency.HIGH: 1,
            HandoffUrgency.MEDIUM: 2,
            HandoffUrgency.LOW: 3,
        }
        return sorted(findings, key=lambda f: urgency_order.get(f.urgency, 4))

    @property
    def all_concerns(self) -> list[str]:
        """All concerns across all handoffs (deduplicated)."""
        seen: set[str] = set()
        concerns: list[str] = []
        for h in self.handoffs:
            for c in h.concerns:
                if c not in seen:
                    seen.add(c)
                    concerns.append(c)
        return concerns

    @property
    def all_suggestions(self) -> list[str]:
        """All suggestions across all handoffs (deduplicated)."""
        seen: set[str] = set()
        suggestions: list[str] = []
        for h in self.handoffs:
            for s in h.suggestions:
                if s not in seen:
                    seen.add(s)
                    suggestions.append(s)
        return suggestions

    def has_critical_concerns(self) -> bool:
        """True if any finding has CRITICAL urgency."""
        return any(
            f.urgency == HandoffUrgency.CRITICAL
            for h in self.handoffs
            for f in h.findings
        )

    def has_high_urgency(self) -> bool:
        """True if any finding has HIGH or CRITICAL urgency."""
        return any(
            f.urgency in (HandoffUrgency.HIGH, HandoffUrgency.CRITICAL)
            for h in self.handoffs
            for f in h.findings
        )

    def to_planner_context(self) -> str:
        """Format all collected handoffs as planner context.

        Produces a combined summary plus individual handoff details.

        Returns:
            Formatted string for injection into planner context
        """
        if not self.handoffs:
            return ""

        lines = [
            "# Worker Handoffs",
            "",
            f"**Workers reported**: {len(self.handoffs)} "
            f"({self.success_count} succeeded, {self.failure_count} failed)",
            "",
        ]

        # High-urgency findings first
        critical_findings = [
            f for f in self.all_findings
            if f.urgency in (HandoffUrgency.CRITICAL, HandoffUrgency.HIGH)
        ]
        if critical_findings:
            lines.append("## Urgent Findings")
            for f in critical_findings:
                lines.append(f"- **[{f.urgency.value.upper()}]** {f.description}")
            lines.append("")

        # Aggregated concerns
        concerns = self.all_concerns
        if concerns:
            lines.append("## Concerns")
            for c in concerns:
                lines.append(f"- {c}")
            lines.append("")

        # Aggregated suggestions
        suggestions = self.all_suggestions
        if suggestions:
            lines.append("## Suggestions for Next Cycle")
            for s in suggestions:
                lines.append(f"- {s}")
            lines.append("")

        # Individual handoffs
        lines.append("---")
        lines.append("")
        for h in self.handoffs:
            lines.append(h.to_planner_context())
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)
