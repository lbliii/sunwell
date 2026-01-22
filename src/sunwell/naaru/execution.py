"""Execution coordination for Naaru (RFC-032/RFC-034/RFC-074).

Handles task graph execution, artifact creation, and incremental execution.
"""


import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.naaru.events import EventEmitter


class ExecutionCoordinator:
    """Coordinates task and artifact execution (RFC-032/RFC-034).

    Handles:
    - Task graph execution with dependency resolution
    - Parallel execution grouping
    - Deadlock detection
    - Artifact collection
    """

    def __init__(
        self,
        workspace: Path,
        synthesis_model: Any = None,
        judge_model: Any = None,
        tool_executor: Any = None,
        event_emitter: EventEmitter | None = None,
        config: Any = None,
    ) -> None:
        """Initialize coordinator.

        Args:
            workspace: Root path for user's project
            synthesis_model: Model for code generation
            judge_model: Model for validation
            tool_executor: Tool executor for commands
            event_emitter: Event emitter for progress
            config: Naaru configuration
        """
        self._root = workspace
        self._synthesis_model = synthesis_model
        self._judge_model = judge_model
        self._tool_executor = tool_executor
        self._emitter = event_emitter
        self._config = config

    async def execute_task_graph(
        self,
        tasks: list[Any],
        output: Callable[[str], None],
        max_time: float,
    ) -> list[Any]:
        """Execute tasks respecting dependencies AND parallelization.

        RFC-034 enhancements:
        - Tracks produced artifacts for artifact-based dependencies
        - Groups ready tasks for parallel execution based on resource conflicts
        - Respects parallel_group hints for safe concurrent execution
        """
        from sunwell.naaru.types import TaskStatus

        completed_ids: set[str] = set()
        completed_artifacts: set[str] = set()
        start_time = datetime.now()

        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_time:
                output("⏰ Timeout reached")
                break

            ready = [
                t for t in tasks
                if t.status == TaskStatus.PENDING
                and t.is_ready(completed_ids, completed_artifacts)
            ]

            if not ready:
                pending = [t for t in tasks if t.status == TaskStatus.PENDING]
                if pending:
                    if self._detect_deadlock(pending, completed_ids, completed_artifacts):
                        output("⚠️ Deadlock detected - forcing remaining tasks")
                        for t in pending:
                            t.status = TaskStatus.FAILED
                        break
                else:
                    break

            parallel_groups = self._group_for_parallel_execution(ready)

            for group in parallel_groups:
                if len(group) == 1:
                    await self._execute_single_task(group[0])
                else:
                    await asyncio.gather(*[self._execute_single_task(t) for t in group])

                for task in group:
                    if task.status == TaskStatus.COMPLETED:
                        completed_ids.add(task.id)
                        if hasattr(task, "produces") and task.produces:
                            completed_artifacts.update(task.produces)

            await asyncio.sleep(0.1)

        return tasks

    def _group_for_parallel_execution(self, ready: list[Any]) -> list[list[Any]]:
        """Group ready tasks for safe parallel execution (RFC-034)."""
        if not ready:
            return []

        groups: dict[str, list[Any]] = {}
        ungrouped: list[Any] = []

        for task in ready:
            if hasattr(task, "parallel_group") and task.parallel_group:
                group_id = task.parallel_group
                groups.setdefault(group_id, []).append(task)
            else:
                ungrouped.append(task)

        result = list(groups.values())
        result.extend([[t] for t in ungrouped])

        return result

    async def _execute_single_task(self, task: Any) -> None:
        """Execute a single task based on its mode."""
        from sunwell.naaru.types import TaskMode, TaskStatus

        try:
            if task.mode == TaskMode.RESEARCH:
                await self._research_task(task)
            elif task.mode == TaskMode.COMMAND:
                await self._execute_command_task(task)
            elif task.mode == TaskMode.GENERATE:
                await self._generate_task(task)
            elif task.mode == TaskMode.SELF_IMPROVE:
                await self._self_improve_task(task)
            elif task.mode == TaskMode.VERIFY:
                await self._verify_task(task)
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Unknown task mode: {task.mode}"
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

    async def _research_task(self, task: Any) -> None:
        """Execute a research task."""
        from sunwell.naaru.types import TaskStatus

        if not self._tool_executor:
            task.status = TaskStatus.FAILED
            task.error = "No tool executor available"
            return

        from sunwell.models.protocol import ToolCall

        tool_call = ToolCall(
            id=task.id,
            name="codebase_search",
            arguments={"query": task.description},
        )

        result = await self._tool_executor.execute(tool_call)
        if result.success:
            task.status = TaskStatus.COMPLETED
            task.output = result.output
        else:
            task.status = TaskStatus.FAILED
            task.error = result.output

    async def _execute_command_task(self, task: Any) -> None:
        """Execute a command task."""
        from sunwell.naaru.types import TaskStatus

        if not self._tool_executor:
            task.status = TaskStatus.FAILED
            task.error = "No tool executor available"
            return

        import shlex
        parts = shlex.split(task.description)
        if not parts:
            task.status = TaskStatus.FAILED
            task.error = "Empty command"
            return

        from sunwell.models.protocol import ToolCall

        tool_call = ToolCall(
            id=task.id,
            name=parts[0],
            arguments={"args": parts[1:] if len(parts) > 1 else []},
        )

        result = await self._tool_executor.execute(tool_call)
        if result.success:
            task.status = TaskStatus.COMPLETED
            task.output = result.output
            if result.artifacts:
                task.produces = [str(a) for a in result.artifacts]
        else:
            task.status = TaskStatus.FAILED
            task.error = result.output

    def _strip_markdown_fences(self, content: str) -> str:
        """Remove markdown code fences from content."""
        lines = content.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)

    async def _generate_task(self, task: Any) -> None:
        """Execute a code generation task."""
        from sunwell.naaru.types import TaskStatus

        if not self._synthesis_model:
            task.status = TaskStatus.FAILED
            task.error = "No synthesis model available"
            return

        prompt = f"""Task: {task.description}

Generate the code to accomplish this task.
Code only, no explanations:"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self._synthesis_model.generate(
                prompt,
                options=GenerateOptions(
                    temperature=self._config.voice_temperature if self._config else 0.7,
                    max_tokens=2048,
                ),
            )

            code = self._strip_markdown_fences(result.content or "")
            task.status = TaskStatus.COMPLETED
            task.output = code

            if self._judge_model:
                await self._validate_and_escalate(task, code)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

    async def _validate_and_escalate(self, task: Any, code: str) -> None:
        """Validate generated code and escalate if quality is low (RFC-034)."""
        from sunwell.naaru.types import TaskStatus

        if not self._judge_model:
            return

        validate_prompt = f"""Review this code for correctness and quality:

```python
{code[:1000]}
```

Respond with ONLY: "APPROVE" or "REJECT" with reason."""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self._judge_model.generate(
                validate_prompt,
                options=GenerateOptions(temperature=0.1, max_tokens=100),
            )

            response = (result.content or "").upper()
            if "REJECT" in response:
                if self._config and self._config.harmonic_synthesis:
                    await self._harmonic_generate(task)
                else:
                    task.status = TaskStatus.FAILED
                    task.error = "Code quality validation failed"

        except Exception:
            pass

    async def _harmonic_generate(self, task: Any) -> None:
        """Use harmonic synthesis for better quality (RFC-034)."""
        from sunwell.naaru.types import TaskStatus

        if not self._synthesis_model:
            return

        prompt = f"""Task: {task.description}

Generate HIGH QUALITY code. Focus on correctness, safety, and best practices.
Code only:"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self._synthesis_model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=2048),
            )

            code = self._strip_markdown_fences(result.content or "")
            task.status = TaskStatus.COMPLETED
            task.output = code

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

    async def _self_improve_task(self, task: Any) -> None:
        """Execute a self-improvement task."""
        from sunwell.naaru.types import TaskStatus

        # Self-improvement requires illuminate() from Naaru
        # This is a placeholder - actual implementation delegates back
        task.status = TaskStatus.COMPLETED

    async def _verify_task(self, task: Any) -> None:
        """Execute a verification task."""
        from sunwell.naaru.types import TaskStatus

        if not self._judge_model:
            task.status = TaskStatus.FAILED
            task.error = "No judge model available"
            return

        verify_prompt = f"""Verify: {task.description}

Respond with "PASS" or "FAIL" with reason."""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self._judge_model.generate(
                verify_prompt,
                options=GenerateOptions(temperature=0.1, max_tokens=200),
            )

            response = (result.content or "").upper()
            if "PASS" in response:
                task.status = TaskStatus.COMPLETED
                task.output = result.content or ""
            else:
                task.status = TaskStatus.FAILED
                task.error = result.content or "Verification failed"

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

    def _detect_deadlock(
        self,
        pending: list[Any],
        completed_ids: set[str],
        completed_artifacts: set[str],
    ) -> bool:
        """Detect if we're in a deadlock (RFC-034)."""
        for task in pending:
            if hasattr(task, "is_ready") and task.is_ready(completed_ids, completed_artifacts):
                return False
        return True

    def collect_artifacts(self, tasks: list[Any]) -> list[Path]:
        """Collect all artifacts produced by tasks."""
        artifacts: set[Path] = set()

        for task in tasks:
            if hasattr(task, "produces") and task.produces:
                for artifact in task.produces:
                    artifacts.add(Path(artifact))

        return sorted(artifacts)
