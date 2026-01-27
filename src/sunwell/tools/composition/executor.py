"""Executor for composed tools.

Handles step-by-step execution with rollback support.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sunwell.tools.composition.composed import ComposedTool, ToolStep
from sunwell.tools.core.types import ToolResult

if TYPE_CHECKING:
    from sunwell.tools.execution.executor import ToolExecutor

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result of executing a single step."""

    step_index: int
    tool_name: str
    success: bool
    output: str
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class ComposedResult:
    """Result of executing a composed tool."""

    name: str
    success: bool
    steps_completed: int
    steps_total: int
    step_results: tuple[StepResult, ...]
    rollback_performed: bool = False
    rollback_results: tuple[StepResult, ...] = ()
    error: str | None = None

    @property
    def summary(self) -> str:
        """Get a summary of the execution."""
        status = "✓" if self.success else "✗"
        parts = [f"{status} {self.name}: {self.steps_completed}/{self.steps_total} steps"]

        if self.rollback_performed:
            parts.append(f" (rolled back {len(self.rollback_results)} steps)")

        if self.error:
            parts.append(f"\nError: {self.error}")

        return "".join(parts)


@dataclass
class ComposedToolExecutor:
    """Executor for composed tools.

    Handles:
    - Sequential step execution
    - Template argument resolution
    - Conditional step execution
    - Automatic rollback on failure

    Example:
        from sunwell.tools.execution import ToolExecutor
        from sunwell.tools.composition import ComposedToolExecutor, CREATE_MODULE

        tool_executor = ToolExecutor(project=project)
        composed_executor = ComposedToolExecutor(tool_executor)

        result = await composed_executor.execute(
            CREATE_MODULE,
            {"module_path": "src/mymodule", "module_name": "mymodule"}
        )

        print(result.summary)
    """

    tool_executor: ToolExecutor
    """The underlying tool executor."""

    _execution_log: list[StepResult] = field(default_factory=list, init=False)
    """Log of step executions for debugging."""

    async def execute(
        self,
        composed_tool: ComposedTool,
        arguments: dict[str, Any],
    ) -> ComposedResult:
        """Execute a composed tool.

        Args:
            composed_tool: The composed tool to execute
            arguments: Input arguments for the composed tool

        Returns:
            ComposedResult with step results and rollback info
        """
        step_results: list[StepResult] = []
        completed_steps: list[tuple[ToolStep, dict[str, Any]]] = []
        error: str | None = None

        logger.info("Executing composed tool: %s", composed_tool.name)

        for i, step in enumerate(composed_tool.steps):
            # Check condition
            if not step.should_run(arguments):
                step_results.append(StepResult(
                    step_index=i,
                    tool_name=step.tool_name,
                    success=True,
                    output="(skipped by condition)",
                    skipped=True,
                ))
                continue

            # Resolve arguments
            resolved_args = step.get_resolved_arguments(arguments)

            logger.debug(
                "Step %d: %s(%s)",
                i, step.tool_name,
                {k: v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v
                 for k, v in resolved_args.items()}
            )

            # Create tool call
            from sunwell.models import ToolCall

            tool_call = ToolCall(
                id=f"composed_{composed_tool.name}_{i}",
                name=step.tool_name,
                arguments=resolved_args,
            )

            # Execute
            try:
                result = await self.tool_executor.execute(tool_call)

                step_results.append(StepResult(
                    step_index=i,
                    tool_name=step.tool_name,
                    success=result.success,
                    output=result.output,
                ))

                if result.success:
                    completed_steps.append((step, resolved_args))
                else:
                    error = f"Step {i} ({step.tool_name}) failed: {result.output}"
                    if composed_tool.stop_on_error:
                        break

            except Exception as e:
                logger.exception("Step %d failed with exception", i)
                step_results.append(StepResult(
                    step_index=i,
                    tool_name=step.tool_name,
                    success=False,
                    output=str(e),
                ))
                error = f"Step {i} ({step.tool_name}) raised exception: {e}"
                if composed_tool.stop_on_error:
                    break

        # Determine overall success
        all_success = all(r.success for r in step_results if not r.skipped)
        steps_completed = sum(1 for r in step_results if r.success and not r.skipped)

        # Perform rollback if needed
        rollback_results: list[StepResult] = []
        rollback_performed = False

        if not all_success and composed_tool.rollback_on_failure and completed_steps:
            logger.info("Rolling back %d completed steps", len(completed_steps))
            rollback_performed = True

            rollback_actions = composed_tool.get_rollback_actions(completed_steps)
            for j, (tool_name, rollback_args) in enumerate(rollback_actions):
                from sunwell.models import ToolCall

                rollback_call = ToolCall(
                    id=f"rollback_{composed_tool.name}_{j}",
                    name=tool_name,
                    arguments=rollback_args,
                )

                try:
                    result = await self.tool_executor.execute(rollback_call)
                    rollback_results.append(StepResult(
                        step_index=j,
                        tool_name=tool_name,
                        success=result.success,
                        output=result.output,
                    ))
                except Exception as e:
                    logger.warning("Rollback step %d failed: %s", j, e)
                    rollback_results.append(StepResult(
                        step_index=j,
                        tool_name=tool_name,
                        success=False,
                        output=str(e),
                    ))

        return ComposedResult(
            name=composed_tool.name,
            success=all_success,
            steps_completed=steps_completed,
            steps_total=len(composed_tool.steps),
            step_results=tuple(step_results),
            rollback_performed=rollback_performed,
            rollback_results=tuple(rollback_results),
            error=error,
        )

    async def execute_by_name(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ComposedResult:
        """Execute a built-in composed tool by name.

        Args:
            name: Name of the built-in composed tool
            arguments: Input arguments

        Returns:
            ComposedResult

        Raises:
            KeyError: If tool name is not found
        """
        from sunwell.tools.composition.composed import BUILTIN_COMPOSED_TOOLS

        if name not in BUILTIN_COMPOSED_TOOLS:
            available = ", ".join(BUILTIN_COMPOSED_TOOLS.keys())
            raise KeyError(f"Unknown composed tool '{name}'. Available: {available}")

        return await self.execute(BUILTIN_COMPOSED_TOOLS[name], arguments)
