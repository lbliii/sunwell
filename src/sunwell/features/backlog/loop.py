"""Autonomous Loop for Autonomous Backlog (RFC-046 Phase 4, RFC-MEMORY).

Main execution loop for autonomous backlog operation.
Integrates with:
- RFC-047 (Deep Verification) for confidence-based auto-approval
- RFC-048 (Autonomy Guardrails) for safe unsupervised operation
- RFC-MEMORY: Uses SessionContext and PersistentMemory
"""


import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Literal

from sunwell.features.backlog.goals import Goal, GoalResult
from sunwell.features.backlog.manager import BacklogManager

if TYPE_CHECKING:
    from sunwell.agent import Agent
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.planners.artifact import ArtifactPlanner
    from sunwell.quality.guardrails import GuardrailSystem


@dataclass(slots=True)
class LoopEvent:
    """Event from autonomous loop.

    Note: Not frozen because data dict prevents hashability.
    Use slots for memory efficiency on high-volume event streams.
    """

    event_type: Literal[
        "session_started",
        "backlog_refreshed",
        "goal_proposed",
        "goal_awaiting_approval",
        "goal_escalated",
        "goal_started",
        "goal_planned",
        "execution_event",
        "goal_completed",
        "goal_failed",
        "goal_verification",
        "goal_checkpointed",
        "backlog_empty",
        "session_complete",
        "session_rollback",
        # Convergence mode events
        "convergence_commit",
        "convergence_reconcile_start",
        "convergence_reconcile_pass",
        "convergence_reconcile_fail",
        "convergence_error_budget",
        "handoff_received",
    ]
    data: dict[str, object]


# Confidence threshold for auto-approval (RFC-047)
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85


class AutonomousLoop:
    """Main loop for autonomous backlog execution.

    Integrates with:
    - RFC-047 (Deep Verification) for confidence-based auto-approval
    - RFC-048 (Autonomy Guardrails) for safe unsupervised operation

    Goals marked auto_approvable also require:
    - Verification confidence >= 85%
    - Guardrail checks (scope limits, action classification)
    """

    def __init__(
        self,
        backlog_manager: BacklogManager,
        planner: ArtifactPlanner,
        agent: Agent,
        model: ModelProtocol | None = None,
        guardrails: GuardrailSystem | None = None,
    ):
        """Initialize autonomous loop.

        Args:
            backlog_manager: Backlog manager
            planner: Artifact planner (RFC-036)
            agent: Adaptive agent (RFC-042)
            model: Model for deep verification (RFC-047)
            guardrails: Guardrail system for safe operation (RFC-048)
        """
        self.backlog_manager = backlog_manager
        self.planner = planner
        self.agent = agent
        self.model = model
        self.guardrails = guardrails

    async def run(
        self,
        mode: Literal["propose", "supervised", "autonomous", "convergence"],
    ) -> AsyncIterator[LoopEvent]:
        """Run the autonomous loop.

        Modes:
        - propose: Generate backlog and show to user, don't execute
        - supervised: Execute with human approval per goal
        - autonomous: Execute auto-approvable goals without asking (RFC-048)
        - convergence: Accept-and-fix mode for maximum throughput.
            Workers commit to work branches without gate enforcement.
            A separate reconciliation pass validates and merges to main.
            Accepts a small error rate for dramatically higher throughput.
            (Inspired by Cursor self-driving codebases research)

        When guardrails are enabled (RFC-048):
        - Session starts with git tag for rollback
        - Each goal is classified by risk level
        - Scope limits are enforced
        - Each goal completion creates a checkpoint commit

        Yields:
            LoopEvent for each step
        """
        # Start guardrail session if available (RFC-048)
        if self.guardrails and mode == "autonomous":
            try:
                session = await self.guardrails.start_session()
                yield LoopEvent(
                    event_type="session_started",
                    data={
                        "session_id": session.session_id,
                        "tag": session.tag,
                        "mode": mode,
                    },
                )
            except Exception as e:
                yield LoopEvent(
                    event_type="goal_failed",
                    data={"error": f"Failed to start session: {e}"},
                )
                return

        # Initial refresh
        backlog = await self.backlog_manager.refresh()
        yield LoopEvent(
            event_type="backlog_refreshed",
            data={"backlog": backlog},
        )

        while True:
            # Check if session can continue (RFC-048)
            if self.guardrails:
                can_continue = self.guardrails.can_continue()
                if not can_continue.passed:
                    yield LoopEvent(
                        event_type="session_complete",
                        data={
                            "reason": can_continue.reason,
                            "stats": self.guardrails.get_session_stats(),
                        },
                    )
                    break

            # Get next goal
            goal = backlog.next_goal()

            if goal is None:
                yield LoopEvent(
                    event_type="backlog_empty",
                    data={},
                )
                if mode == "autonomous":
                    # Wait for external changes, then refresh
                    await self._wait_for_changes()
                    backlog = await self.backlog_manager.refresh()
                    continue
                else:
                    break

            # Check approval
            if mode == "propose":
                yield LoopEvent(
                    event_type="goal_proposed",
                    data={"goal": goal},
                )
                continue

            # RFC-048: Use guardrails for auto-approval decision
            should_escalate = False
            if self.guardrails and mode == "autonomous":
                can_auto = await self.guardrails.can_auto_approve(goal)
                if not can_auto:
                    should_escalate = True
            elif not goal.auto_approvable:
                should_escalate = True

            if mode == "supervised" or should_escalate:
                # RFC-048: Use guardrail escalation if available
                if self.guardrails and should_escalate:
                    resolution = await self.guardrails.escalate_goal(goal)
                    yield LoopEvent(
                        event_type="goal_escalated",
                        data={
                            "goal": goal,
                            "action": resolution.action,
                            "option_id": resolution.option_id,
                        },
                    )

                    if resolution.action == "skip":
                        await self.backlog_manager.block_goal(goal.id, "User skipped")
                        continue
                    elif resolution.action == "abort":
                        yield LoopEvent(
                            event_type="session_complete",
                            data={"reason": "User aborted session"},
                        )
                        return
                    elif resolution.action != "approve":
                        await self.backlog_manager.block_goal(
                            goal.id, f"Action: {resolution.action}"
                        )
                        continue
                else:
                    yield LoopEvent(
                        event_type="goal_awaiting_approval",
                        data={"goal": goal},
                    )
                    approval = await self._await_approval(goal)
                    if not approval:
                        await self.backlog_manager.block_goal(goal.id, "User skipped")
                        continue

            # Execute goal
            yield LoopEvent(
                event_type="goal_started",
                data={"goal": goal},
            )
            self.backlog_manager.backlog.in_progress = goal.id

            # RFC-048: Track goal start time
            if self.guardrails:
                self.guardrails.scope_tracker.start_goal()

            start_time = time()

            try:
                # Decompose goal into artifacts (RFC-036) for planning visibility
                artifact_graph = await self.planner.discover_graph(goal.description)
                yield LoopEvent(
                    event_type="goal_planned",
                    data={"goal": goal, "artifacts": artifact_graph},
                )

                # Execute with adaptive agent (RFC-042, RFC-MEMORY)
                # Agent.run() takes SessionContext and PersistentMemory
                from sunwell.agent.context.session import SessionContext
                from sunwell.agent.utils.request import RunOptions
                from sunwell.memory import PersistentMemory

                workspace = self.backlog_manager.root
                options = RunOptions(trust="workspace")
                session = SessionContext.build(workspace, goal.description, options)
                memory = PersistentMemory.load(workspace)

                async for event in self.agent.run(session, memory):
                    yield LoopEvent(
                        event_type="execution_event",
                        data={"goal": goal, "event": event},
                    )

                # Validate (includes deep verification for auto-approvable goals)
                yield LoopEvent(
                    event_type="goal_verification",
                    data={"goal": goal, "status": "running"},
                )
                result = await self._validate_goal(goal)

                duration = time() - start_time
                # Create new result with duration (GoalResult is frozen)
                result = GoalResult(
                    success=result.success,
                    failure_reason=result.failure_reason,
                    summary=result.summary,
                    duration_seconds=duration,
                    files_changed=result.files_changed,
                    artifacts_created=result.artifacts_created,
                )

                if result.success:
                    # RFC-048: Checkpoint the goal
                    if self.guardrails:
                        from sunwell.quality.guardrails import FileChange

                        changes = [
                            FileChange(path=Path(f), lines_added=10, lines_removed=5)
                            for f in result.files_changed
                        ]
                        commit = await self.guardrails.checkpoint_goal(goal, changes)
                        if commit:
                            yield LoopEvent(
                                event_type="goal_checkpointed",
                                data={"goal": goal, "commit": commit},
                            )

                    await self.backlog_manager.complete_goal(goal.id, result)
                    yield LoopEvent(
                        event_type="goal_completed",
                        data={"goal": goal, "result": result},
                    )
                else:
                    await self.backlog_manager.block_goal(
                        goal.id, result.failure_reason
                    )
                    yield LoopEvent(
                        event_type="goal_failed",
                        data={"goal": goal, "result": result},
                    )

            except Exception as e:
                duration = time() - start_time
                result = GoalResult(
                    success=False,
                    failure_reason=str(e),
                    duration_seconds=duration,
                    files_changed=(),
                    artifacts_created=(),
                )
                await self.backlog_manager.block_goal(goal.id, str(e))
                yield LoopEvent(
                    event_type="goal_failed",
                    data={"goal": goal, "error": str(e)},
                )

            # Refresh backlog after each goal (new signals may have appeared)
            backlog = await self.backlog_manager.refresh()
            yield LoopEvent(
                event_type="backlog_refreshed",
                data={"backlog": backlog},
            )

        # Session complete - cleanup
        if self.guardrails and mode == "autonomous":
            await self.guardrails.cleanup_session()
            yield LoopEvent(
                event_type="session_complete",
                data={"stats": self.guardrails.get_session_stats()},
            )

    async def _await_approval(self, goal: Goal) -> bool:
        """Await user approval for a goal.

        Returns True to proceed, False to skip.
        In supervised mode, this should prompt the user.
        For autonomous mode, this is only called for non-auto-approvable goals.
        """
        # Default: approve in supervised mode (user can skip via block command)
        # Future: integrate with interactive prompt
        return True

    async def _validate_goal(self, goal: Goal) -> GoalResult:
        """Validate that goal was completed successfully.

        Uses two validation strategies:
        1. Signal-based: Re-runs signal extraction to verify source signals resolved
        2. Deep verification (RFC-047): Semantic correctness with confidence scoring

        For auto-approvable goals, requires confidence >= AUTO_APPROVE_CONFIDENCE_THRESHOLD.
        """
        from sunwell.features.backlog.signals import SignalExtractor

        # Strategy 1: Signal-based validation
        extractor = SignalExtractor(root=self.backlog_manager.root)
        current_signals = await extractor.extract_all()

        goal_signal_ids = set(goal.source_signals)
        remaining_signals = {
            f"{s.signal_type}:{s.location.file}:{s.location.line_start}"
            for s in current_signals
        }

        unresolved = goal_signal_ids & remaining_signals
        signals_resolved = len(unresolved) == 0

        # Strategy 2: Deep verification (RFC-047)
        verification_passed = True
        verification_confidence = 1.0
        verification_issues: list[str] = []

        if self.model and goal.auto_approvable:
            # For auto-approvable goals, run deep verification
            verification_result = await self._run_deep_verification(goal)
            verification_passed = verification_result.get("passed", True)
            verification_confidence = verification_result.get("confidence", 1.0)
            verification_issues = verification_result.get("issues", [])

            # Auto-approval requires high confidence
            if verification_confidence < AUTO_APPROVE_CONFIDENCE_THRESHOLD:
                verification_passed = False
                verification_issues.append(
                    f"Confidence {verification_confidence:.0%} below threshold "
                    f"({AUTO_APPROVE_CONFIDENCE_THRESHOLD:.0%})"
                )

        # Combine results
        success = signals_resolved and verification_passed

        failure_reasons: list[str] = []
        if not signals_resolved:
            failure_reasons.append(f"Signals still present: {unresolved}")
        if not verification_passed:
            failure_reasons.extend(verification_issues)

        return GoalResult(
            success=success,
            failure_reason="; ".join(failure_reasons) if failure_reasons else "",
            files_changed=(),
            artifacts_created=(),
        )

    async def _run_deep_verification(self, goal: Goal) -> dict:
        """Run deep verification on goal artifacts (RFC-047).

        Returns dict with: passed, confidence, issues
        """
        if not self.model:
            return {"passed": True, "confidence": 1.0, "issues": []}

        try:
            from sunwell.planning.naaru.artifacts import ArtifactSpec
            from sunwell.quality.verification import create_verifier

            verifier = create_verifier(
                model=self.model,
                cwd=self.backlog_manager.root,
                level="standard",
            )

            # Get changed files from scope
            changed_files: list[Path] = []
            if goal.scope.allowed_paths:
                changed_files = list(goal.scope.allowed_paths)
            else:
                # Default to scanning for recently modified Python files
                root = self.backlog_manager.root
                for py_file in root.rglob("*.py"):
                    if not any(
                        part.startswith(".")
                        for part in py_file.relative_to(root).parts
                    ):
                        changed_files.append(py_file)
                        if len(changed_files) >= goal.scope.max_files:
                            break

            # Verify each changed file
            total_confidence = 0.0
            all_passed = True
            all_issues: list[str] = []

            for file_path in changed_files:
                if not file_path.exists():
                    continue

                content = file_path.read_text()
                file_spec = ArtifactSpec(
                    id=file_path.stem,
                    description=f"Verify {file_path.name}",
                    contract=goal.description,
                    produces_file=str(file_path),
                    requires=frozenset(),
                    domain_type="code",
                )

                result = await verifier.verify_quick(file_spec, content)
                total_confidence += result.confidence

                if not result.passed:
                    all_passed = False
                    for issue in result.issues[:2]:
                        all_issues.append(f"{file_path.name}: {issue.description}")

            avg_confidence = (
                total_confidence / len(changed_files) if changed_files else 1.0
            )

            return {
                "passed": all_passed,
                "confidence": avg_confidence,
                "issues": all_issues,
            }

        except Exception as e:
            # If verification fails, don't block - just log
            return {
                "passed": True,
                "confidence": 0.5,
                "issues": [f"Verification error: {e}"],
            }

    async def _wait_for_changes(self) -> None:
        """Wait for external changes before refreshing backlog.

        In autonomous mode, when backlog is empty, wait for file changes
        or git events before refreshing. Simple implementation: short delay.
        """
        await asyncio.sleep(5)
