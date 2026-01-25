"""Workflow Engine — Procedural workflow executor (RFC-086).

The WorkflowEngine executes multi-step chains with:
- Sequential execution (procedural, not event-driven)
- Checkpoints for user confirmation
- Interruptible steps
- State persistence
- Error recovery
"""


import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from sunwell.workflow.types import (
    WorkflowChain,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepResult,
)

if TYPE_CHECKING:
    from sunwell.core.lens import Lens


class SkillExecutor(Protocol):
    """Protocol for executing skills."""

    async def execute(
        self, skill_name: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a skill and return its output."""
        ...


@dataclass(slots=True)
class WriterContext:
    """Context for workflow execution (RFC-086)."""

    lens: Lens | None
    """Active lens providing expertise."""

    target_file: Path | None
    """Target file being worked on."""

    working_dir: Path
    """Working directory."""

    content: str | None = None
    """Current document content."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Additional context data."""


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Result of workflow execution."""

    status: str
    """Final status: "completed", "paused", "error", "cancelled"."""

    execution: WorkflowExecution
    """Full execution state."""

    error: str | None = None
    """Error message if failed."""

    output_file: Path | None = None
    """Output file if created."""


class StepError(Exception):
    """Error during step execution."""

    def __init__(self, step: WorkflowStep, message: str, recoverable: bool = True):
        super().__init__(message)
        self.step = step
        self.recoverable = recoverable


class WorkflowEngine:
    """Procedural workflow executor with checkpoints and state persistence.

    This is the core of RFC-086's autonomous execution. It runs skill chains
    sequentially, with support for:
    - Checkpoints (pause points for user review)
    - Interruption (user can stop mid-chain)
    - State persistence (resume across sessions)
    - Error recovery (retry/skip/stop options)

    Example:
        >>> engine = WorkflowEngine(state_dir=Path(".sunwell/state"))
        >>> chain = WORKFLOW_CHAINS["feature-docs"]
        >>> context = WriterContext(lens=tech_writer, target_file=Path("docs/api.md"))
        >>> result = await engine.execute(chain, context)
    """

    def __init__(
        self,
        state_dir: Path = Path(".sunwell/state"),
        skill_executor: SkillExecutor | None = None,
    ):
        """Initialize the workflow engine.

        Args:
            state_dir: Directory for state persistence
            skill_executor: Executor for running skills
        """
        self.state_dir = state_dir
        self.skill_executor = skill_executor
        self._interrupted = False
        self._current_execution: WorkflowExecution | None = None

    async def execute(
        self,
        chain: WorkflowChain,
        context: WriterContext,
        resume_from: WorkflowExecution | None = None,
    ) -> WorkflowResult:
        """Execute workflow steps sequentially with checkpoint support.

        Args:
            chain: Workflow chain to execute
            context: Execution context
            resume_from: Previous execution to resume (optional)

        Returns:
            WorkflowResult with final status and execution state
        """
        # Create or resume execution
        if resume_from:
            execution = resume_from
            execution.status = "running"
        else:
            execution = WorkflowExecution(
                id=self._generate_id(chain.name),
                chain=chain,
                context={
                    "lens": context.lens.metadata.name if context.lens else None,
                    "target_file": str(context.target_file) if context.target_file else None,
                    "working_dir": str(context.working_dir),
                },
            )

        self._current_execution = execution
        self._interrupted = False

        # Execute steps
        for i in range(execution.current_step, len(chain.steps)):
            step = chain.steps[i]
            execution.current_step = i
            execution.updated_at = datetime.now()

            # Check for interruption
            if self._interrupted:
                execution.status = "paused"
                await self._persist_state(execution)
                return WorkflowResult(
                    status="paused",
                    execution=execution,
                )

            # Execute step
            try:
                result = await self._execute_step(step, context, execution)
                execution.completed_steps.append(result)

                # Check for step failure
                if result.status == "error":
                    execution.status = "error"
                    return WorkflowResult(
                        status="error",
                        execution=execution,
                        error=result.error,
                    )

                # Checkpoint if configured
                if i in chain.checkpoint_after:
                    await self._persist_state(execution)
                    should_continue = await self._confirm_continue(execution)
                    if not should_continue:
                        execution.status = "paused"
                        return WorkflowResult(
                            status="paused",
                            execution=execution,
                        )

            except StepError as e:
                return await self._handle_step_error(e, execution, context)

        # All steps complete
        execution.status = "completed"
        execution.updated_at = datetime.now()

        return WorkflowResult(
            status="completed",
            execution=execution,
        )

    async def pause(self) -> None:
        """Pause the current execution at next opportunity."""
        self._interrupted = True

    async def resume(self, execution_id: str) -> WorkflowResult:
        """Resume a paused execution.

        Args:
            execution_id: ID of execution to resume

        Returns:
            WorkflowResult after resuming
        """
        from sunwell.workflow.state import WorkflowStateManager

        manager = WorkflowStateManager(self.state_dir)
        state = await manager.load(execution_id)

        if state is None:
            return WorkflowResult(
                status="error",
                execution=WorkflowExecution(
                    id=execution_id,
                    chain=WorkflowChain(name="unknown", description="", steps=()),
                ),
                error=f"Execution {execution_id} not found",
            )

        # Reconstruct execution from state
        from sunwell.workflow.types import WORKFLOW_CHAINS

        chain = WORKFLOW_CHAINS.get(state.chain_name)
        if chain is None:
            return WorkflowResult(
                status="error",
                execution=WorkflowExecution(
                    id=execution_id,
                    chain=WorkflowChain(name=state.chain_name, description="", steps=()),
                ),
                error=f"Unknown workflow chain: {state.chain_name}",
            )

        execution = state.to_execution(chain)

        # Build context from state
        context = WriterContext(
            lens=None,  # Would need lens loader
            target_file=Path(state.target_file) if state.target_file else None,
            working_dir=Path(state.working_dir),
        )

        return await self.execute(chain, context, resume_from=execution)

    async def _execute_step(
        self,
        step: WorkflowStep,
        context: WriterContext,
        execution: WorkflowExecution,
    ) -> WorkflowStepResult:
        """Execute a single workflow step.

        Args:
            step: Step to execute
            context: Execution context
            execution: Parent execution

        Returns:
            Step result
        """
        started_at = datetime.now()

        try:
            # Execute with timeout
            if self.skill_executor:
                output = await asyncio.wait_for(
                    self.skill_executor.execute(
                        step.skill,
                        {
                            "lens": context.lens,
                            "target_file": str(context.target_file) if context.target_file else None,
                            "content": context.content,
                            "working_dir": str(context.working_dir),
                            "previous_steps": [s.to_dict() for s in execution.completed_steps],
                            **context.extra,
                        },
                    ),
                    timeout=step.timeout_s,
                )
            else:
                # Mock execution for testing
                await asyncio.sleep(0.1)
                output = {"mock": True, "skill": step.skill}

            return WorkflowStepResult(
                skill=step.skill,
                status="success",
                started_at=started_at,
                completed_at=datetime.now(),
                output=output,
            )

        except TimeoutError:
            return WorkflowStepResult(
                skill=step.skill,
                status="error",
                started_at=started_at,
                completed_at=datetime.now(),
                error=f"Step timed out after {step.timeout_s}s",
            )

        except Exception as e:
            return WorkflowStepResult(
                skill=step.skill,
                status="error",
                started_at=started_at,
                completed_at=datetime.now(),
                error=str(e),
            )

    async def _handle_step_error(
        self,
        error: StepError,
        execution: WorkflowExecution,
        context: WriterContext,
    ) -> WorkflowResult:
        """Handle a step error.

        Args:
            error: The step error
            execution: Current execution state
            context: Execution context

        Returns:
            WorkflowResult with error status
        """
        execution.status = "error"
        execution.updated_at = datetime.now()

        # Add failed step to completed with error status
        execution.completed_steps.append(
            WorkflowStepResult(
                skill=error.step.skill,
                status="error",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                error=str(error),
            )
        )

        await self._persist_state(execution)

        return WorkflowResult(
            status="error",
            execution=execution,
            error=str(error),
        )

    async def _persist_state(self, execution: WorkflowExecution) -> None:
        """Persist execution state to disk.

        Uses atomic write (temp file + rename) for safety.
        """
        from sunwell.workflow.state import WorkflowStateManager

        manager = WorkflowStateManager(self.state_dir)
        await manager.save(execution)

    async def _confirm_continue(self, execution: WorkflowExecution) -> bool:
        """Ask user to confirm continuation at checkpoint.

        In headless mode, always returns True.
        In interactive mode, would show prompt.

        Returns:
            True to continue, False to pause
        """
        # Default: continue (headless mode)
        # In interactive mode, this would show a prompt
        return True

    def _generate_id(self, chain_name: str) -> str:
        """Generate a unique execution ID."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        short_uuid = uuid.uuid4().hex[:8]
        return f"wf-{timestamp}-{chain_name}-{short_uuid}"

    def get_current_execution(self) -> WorkflowExecution | None:
        """Get the currently running execution, if any."""
        return self._current_execution
