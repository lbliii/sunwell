"""Task execution helpers for Agent.

Provides task and gate execution functionality that the Agent delegates to.
Extracted to keep Agent class focused on orchestration.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    lens_selected_event,
    model_complete_event,
    model_start_event,
    model_thinking_event,
    model_tokens_event,
)
from sunwell.agent.utils.thinking import ThinkingDetector
from sunwell.agent.validation import Artifact, ValidationStage

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore
    from sunwell.agent.utils.metrics import InferenceMetrics
    from sunwell.agent.validation.gates import ValidationGate
    from sunwell.foundation.core.lens import Lens
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.types import Task

logger = logging.getLogger(__name__)


async def execute_task_streaming_fallback(
    task: Task,
    model: ModelProtocol,
    cwd: Path,
    learning_store: LearningStore,
    inference_metrics: InferenceMetrics,
    workspace_context: str | None = None,
    token_batch_size: int = 10,
) -> AsyncIterator[tuple[AgentEvent, str | None]]:
    """Execute task via text streaming (fallback path).

    This is the original streaming implementation used when tool-based
    execution is unavailable or fails.

    Args:
        task: The task to execute
        model: Model for generation
        cwd: Working directory
        learning_store: For formatting learnings context
        inference_metrics: For tracking inference performance
        workspace_context: Optional workspace context
        token_batch_size: Batch size for token events

    Yields:
        Tuples of (event, result_text) where result_text is set on final yield
    """
    from sunwell.models import GenerateOptions

    learnings_context = learning_store.format_for_prompt(5)

    # Build context sections
    context_sections = []
    if workspace_context:
        context_sections.append(workspace_context)
    if learnings_context:
        context_sections.append(f"KNOWN FACTS:\n{learnings_context}")

    context_block = "\n\n".join(context_sections) if context_sections else ""

    # Detect if task is code generation (has target_path) or conversational
    if task.target_path:
        prompt = f"""Generate code for this task:

TASK: {task.description}

{context_block}

Output ONLY the code (no explanation, no markdown fences):"""
    else:
        # Conversational task - allow natural response
        prompt = f"""Complete this task:

TASK: {task.description}

{context_block}

Respond directly and helpfully:"""

    prompt_tokens = len(prompt) // 4
    model_id = getattr(model, "model_id", "unknown")
    estimated_time = inference_metrics.estimate_time(model_id, prompt_tokens, expected_output=500)

    yield (
        model_start_event(
            task_id=task.id,
            model=model_id,
            prompt_tokens=prompt_tokens,
            estimated_time_s=estimated_time,
        ),
        None,
    )

    start_time = time()
    first_token_time: float | None = None
    token_buffer: list[str] = []
    token_count = 0
    thinking_detector = ThinkingDetector()

    # Check if model supports streaming, fall back to non-streaming if not
    has_streaming = hasattr(model, "generate_stream") and callable(
        getattr(model, "generate_stream", None)
    )

    if has_streaming:
        async for chunk in model.generate_stream(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=4000),
        ):
            if first_token_time is None:
                first_token_time = time()

            token_buffer.append(chunk)
            token_count += 1

            thinking_blocks = thinking_detector.feed(chunk)
            for block in thinking_blocks:
                yield (
                    model_thinking_event(
                        task_id=task.id,
                        phase=block.phase,
                        content=block.content,
                        is_complete=block.is_complete,
                    ),
                    None,
                )

            elapsed = time() - start_time
            if token_count % token_batch_size == 0:
                tps = token_count / elapsed if elapsed > 0 else None
                yield (
                    model_tokens_event(
                        task_id=task.id,
                        tokens="".join(token_buffer[-token_batch_size:]),
                        token_count=token_count,
                        tokens_per_second=tps,
                    ),
                    None,
                )
    else:
        # Fallback for models without streaming support
        result = await model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=4000),
        )
        if result.text:
            token_buffer = [result.text]
            token_count = len(result.text) // 4
            first_token_time = time()

    duration = time() - start_time
    tps = token_count / duration if duration > 0 else 0
    ttft_ms = int((first_token_time - start_time) * 1000) if first_token_time else None

    inference_metrics.record(
        model=model_id,
        duration_s=duration,
        tokens=token_count,
        ttft_ms=ttft_ms,
    )

    yield (
        model_complete_event(
            task_id=task.id,
            total_tokens=token_count,
            duration_s=duration,
            tokens_per_second=tps,
            time_to_first_token_ms=ttft_ms,
        ),
        "".join(token_buffer),
    )


async def validate_gate(
    gate: ValidationGate,
    artifacts: list[Artifact],
    cwd: Path,
) -> AsyncIterator[AgentEvent]:
    """Validate at a gate.

    Args:
        gate: The validation gate to run
        artifacts: Artifacts to validate
        cwd: Working directory

    Yields:
        Validation events
    """
    validation_stage = ValidationStage(cwd)
    gate_artifacts = {gate.id: artifacts}

    async for event in validation_stage.validate_all([gate], gate_artifacts):
        yield event


def determine_specialist_role(task: Task) -> str:
    """Determine the appropriate specialist role for a task.

    Args:
        task: The task to analyze

    Returns:
        Role name (e.g., "code_reviewer", "architect", "debugger")
    """
    description_lower = task.description.lower()

    # Match patterns to roles
    if any(kw in description_lower for kw in ["review", "audit", "check"]):
        return "code_reviewer"
    if any(kw in description_lower for kw in ["design", "architect", "structure"]):
        return "architect"
    if any(kw in description_lower for kw in ["debug", "fix", "investigate"]):
        return "debugger"
    if any(kw in description_lower for kw in ["test", "verify", "validate"]):
        return "tester"
    if any(kw in description_lower for kw in ["document", "explain", "describe"]):
        return "documentarian"
    if any(kw in description_lower for kw in ["security", "auth", "encrypt"]):
        return "security_specialist"
    if any(kw in description_lower for kw in ["optimize", "performance", "speed"]):
        return "optimizer"

    # Default
    return "specialist"


def should_spawn_specialist(
    task: Task,
    lens: Lens | None,
    specialist_count: int,
    has_naaru: bool,
) -> bool:
    """Decide if task should be delegated to a specialist.

    Spawning is triggered when:
    1. Lens has can_spawn enabled
    2. Task complexity exceeds threshold (estimated_complexity > 0.8)
    3. OR task requires tools not in current lens
    4. AND we haven't exceeded max_children

    Args:
        task: The task to evaluate
        lens: Current lens (if any)
        specialist_count: Number of specialists already spawned
        has_naaru: Whether Naaru is available

    Returns:
        True if task should be delegated to specialist
    """
    # Check if spawning is enabled
    if not lens or not lens.can_spawn:
        return False

    # Check spawn limit
    if specialist_count >= lens.max_children:
        return False

    # Check Naaru is available
    if not has_naaru:
        return False

    # Check task complexity (if available)
    estimated_complexity = getattr(task, "estimated_complexity", 0.0)
    if estimated_complexity > 0.8:
        return True

    # Check if task requires specialized tools
    required_tools = set(getattr(task, "required_tools", []))
    if required_tools:
        available_tools = set(lens.skills) if lens.skills else set()
        if not required_tools.issubset(available_tools):
            return True

    return False


async def select_lens_for_task(
    task: Task,
    cwd: Path,
    auto_lens: bool,
) -> Lens | None:
    """Select the best-fit lens for a specific task (lens rotation).

    Different tasks may benefit from different expertise:
    - Database task → database lens
    - Frontend task → frontend lens
    - API task → API lens

    Args:
        task: The task to select lens for
        cwd: Working directory
        auto_lens: Whether auto-lens selection is enabled

    Returns:
        Best lens for this task, or None to use current lens
    """
    from sunwell.agent.utils.lens import resolve_lens_for_goal

    # Skip if no auto-lens or task doesn't have a clear domain
    if not auto_lens:
        return None

    # Use task description + target path for lens selection
    task_hint = task.description
    if task.target_path:
        task_hint = f"{task.target_path}: {task_hint}"

    try:
        resolution = await resolve_lens_for_goal(
            goal=task_hint,
            project_path=cwd,
            auto_select=True,
        )
        if resolution.lens and resolution.confidence > 0.7:
            return resolution.lens
    except Exception as e:
        logger.debug("Lens resolution failed for task %s: %s", task.id, e)

    return None


async def execute_task_with_tools(
    task: Task,
    model: ModelProtocol,
    tool_executor: Any,
    cwd: Path,
    learning_store: LearningStore,
    inference_metrics: InferenceMetrics,
    workspace_context: str | None,
    lens: Lens | None,
    memory: Any | None,
    simulacrum: Any | None,
    current_options: Any | None,
    smart_model: ModelProtocol | None,
    delegation_model: ModelProtocol | None,
    auto_lens: bool = True,
) -> AsyncIterator[tuple[AgentEvent, str | None, Any]]:
    """Execute task via AgentLoop with native tool calling (preferred path).

    Enhancements over basic tool calling:
    - Lens rotation: Selects best-fit lens per task
    - Task memory: Injects task-specific constraints/hazards/patterns
    - Validation gates: Runs lint/syntax checks after file writes
    - Recovery integration: Saves state on failures for later resume

    Args:
        task: The task to execute
        model: Primary model for generation
        tool_executor: Tool executor
        cwd: Working directory
        learning_store: For tracking learnings
        inference_metrics: For tracking inference performance
        workspace_context: Workspace context string
        lens: Current lens
        memory: PersistentMemory reference
        simulacrum: SimulacrumStore for knowledge
        current_options: RunOptions for this execution
        smart_model: Smart model for lens creation (RFC-137)
        delegation_model: Cheap model for delegation (RFC-137)
        auto_lens: Whether auto-lens selection is enabled

    Yields:
        Tuples of (event, result_text, tracker) where result_text is set on completion
    """
    from sunwell.agent.core import AgentLoop
    from sunwell.agent.core.task_graph import sanitize_code_content
    from sunwell.agent.events import AgentEvent, EventType
    from sunwell.agent.loop import LoopConfig
    from sunwell.agent.validation import ValidationStage
    from sunwell.tools.tracking import InvocationTracker

    # === LENS ROTATION: Select best lens for this specific task ===
    task_lens = await select_lens_for_task(task, cwd, auto_lens)
    if task_lens and task_lens != lens:
        yield (
            lens_selected_event(
                name=task_lens.metadata.name,
                source="task_rotation",
            ),
            None,
            None,
        )

    # === BUILD CONTEXT: Learnings + Task Memory + Lens ===
    context_sections = []

    # Workspace context (ToC, structure)
    if workspace_context:
        context_sections.append(workspace_context)

    # Learnings from past runs
    learnings_context = learning_store.format_for_prompt(5)
    if learnings_context:
        context_sections.append(f"KNOWN FACTS:\n{learnings_context}")

    # Task-specific memory (constraints, hazards, patterns)
    if memory:
        task_memory = memory.get_task_context(task)
        if task_memory:
            context_sections.append(f"TASK CONTEXT:\n{task_memory.to_prompt()}")

    # Lens expertise (heuristics, patterns, anti-patterns)
    active_lens = task_lens or lens
    if active_lens:
        context_sections.append(f"EXPERTISE:\n{active_lens.to_context()}")

    context_block = "\n\n".join(context_sections) if context_sections else None

    # === BUILD SYSTEM PROMPT ===
    system_prompt = (
        "You are a code generation assistant. When you need to create or modify files, "
        "use the write_file or edit_file tools. Do NOT output code in your text response - "
        "always use the appropriate file tool to write code to disk. "
        "The write_file content parameter expects RAW code, not wrapped in markdown."
    )

    # === CREATE LOOP CONFIG ===
    # Get delegation settings from current options (RFC-137)
    enable_delegation = False
    delegation_threshold = 2000
    if current_options:
        enable_delegation = current_options.enable_delegation
        delegation_threshold = current_options.delegation_threshold_tokens

    config = LoopConfig(
        max_turns=15,
        temperature=0.3,
        tool_choice="auto",
        enable_learning_injection=True,
        enable_validation_gates=True,  # Run lint/syntax after file writes
        enable_recovery=True,  # Save state on failures
        # RFC-137: Smart-to-dumb model delegation
        enable_delegation=enable_delegation,
        delegation_threshold_tokens=delegation_threshold,
    )

    # === CREATE VALIDATION STAGE (for inner-loop validation) ===
    validation_stage = ValidationStage(cwd)

    # === CREATE MIRROR HANDLER (for self-reflection) ===
    mirror_handler = None
    try:
        from sunwell.features.mirror.handler import MirrorHandler

        mirror_handler = MirrorHandler(
            workspace=cwd,
            storage_path=cwd / ".sunwell" / "mirror",
            lens=active_lens,
            simulacrum=simulacrum,
            executor=tool_executor,
        )
    except ImportError:
        pass  # Mirror feature not installed
    except Exception as e:
        logger.debug("Mirror handler initialization failed: %s", e)

    # === RESOLVE DELEGATION MODELS (RFC-137) ===
    from sunwell.models import resolve_model

    smart_model_resolved = None
    delegation_model_resolved = None

    if enable_delegation:
        # Resolve smart model: Agent field → RunOptions → primary model
        if smart_model is not None:
            smart_model_resolved = smart_model
        elif current_options and current_options.smart_model:
            smart_model_resolved = resolve_model(
                current_options.smart_model,
                fallback=model,
            )
        else:
            smart_model_resolved = model  # Use primary as smart

        # Resolve delegation model: Agent field → RunOptions → None
        if delegation_model is not None:
            delegation_model_resolved = delegation_model
        elif current_options and current_options.delegation_model:
            delegation_model_resolved = resolve_model(
                current_options.delegation_model,
            )

    # === CREATE AND RUN THE LOOP ===
    loop = AgentLoop(
        model=model,
        executor=tool_executor,
        config=config,
        learning_store=learning_store,
        validation_stage=validation_stage,
        lens=active_lens,  # For expertise injection
        mirror_handler=mirror_handler,  # For self-reflection
        # RFC-137: Model delegation
        smart_model=smart_model_resolved,
        delegation_model=delegation_model_resolved,
    )

    # Initialize invocation tracker for this task
    tracker = InvocationTracker(task_id=task.id)

    start_time = time()
    tool_results: list[str] = []
    model_text_output: list[str] = []  # Capture text in case we need to self-correct

    async for event in loop.run(
        task_description=task.description,
        system_prompt=system_prompt,
        context=context_block,
    ):
        yield (event, None, None)

        # Track ALL tool invocations via the tracker
        if event.type.value == "tool_complete":
            data = event.data
            tool_name = data.get("tool_name", "unknown")
            tracker.record(
                tool_name=tool_name,
                arguments=data.get("arguments", {}),
                result=data.get("output"),
                success=data.get("success", False),
                error=data.get("error"),
            )

            # Track successful file writes for result
            if tool_name in ("write_file", "edit_file") and data.get("success"):
                tool_results.append(data.get("output", ""))

        # Capture model's text output (for self-correction if needed)
        if event.type.value == "tool_loop_complete":
            final_response = event.data.get("final_response")
            if final_response:
                model_text_output.append(final_response)

    duration = time() - start_time

    # Set the task result
    result_text = "\n".join(tool_results) if tool_results else ""

    # SELF-CORRECTION: Verify expected outcomes based on task type

    if task.target_path:
        expected_path = cwd / task.target_path

        # Check if write_file was actually called
        write_file_called = tracker.was_called("write_file") or tracker.was_called(
            "edit_file"
        )

        if not expected_path.exists() and not write_file_called:
            # Tool wasn't called - check if model output something we can use
            text_output = "\n".join(model_text_output).strip()

            if text_output:
                # Self-correct: model output code in text, write it ourselves
                logger.info(
                    "Self-correcting: Task %s - write_file not called, using text for %s",
                    task.id,
                    task.target_path,
                )

                # Sanitize and write the file
                expected_path.parent.mkdir(parents=True, exist_ok=True)
                sanitized = sanitize_code_content(text_output)
                expected_path.write_text(sanitized)
                result_text = sanitized

                # Record the self-correction in the tracker
                tracker.record(
                    tool_name="write_file",
                    arguments={"path": task.target_path, "content": sanitized[:100] + "..."},
                    result="Self-corrected",
                    success=True,
                    self_corrected=True,
                )

                # Emit self-correction event
                yield (
                    AgentEvent(
                        type=EventType.TOOL_COMPLETE,
                        data={
                            "tool_name": "write_file",
                            "success": True,
                            "output": f"Self-corrected: wrote {task.target_path}",
                            "self_corrected": True,
                            "invocation_summary": tracker.summary(),
                        },
                    ),
                    result_text,
                    tracker,
                )
                return
            else:
                # No text output either - this is a real failure
                logger.warning(
                    "Task %s: write_file not called and no text output for %s",
                    task.id,
                    task.target_path,
                )
                yield (
                    AgentEvent(
                        type=EventType.VALIDATE_ERROR,
                        data={
                            "message": f"Expected file {task.target_path} was not created",
                            "task_id": task.id,
                            "step": "file_creation",
                            "invocation_summary": tracker.summary(),
                        },
                    ),
                    None,
                    tracker,
                )
                # Raise to trigger fallback
                raise RuntimeError(
                    f"Task {task.id} did not create expected file {task.target_path}"
                )

    # Record metrics
    model_id = getattr(model, "model_id", "unknown")
    inference_metrics.record(
        model=model_id,
        duration_s=duration,
        tokens=0,  # Token count from tool loop not easily available
        ttft_ms=None,
    )

    # Final yield with task completion event (not None)
    yield (
        AgentEvent(
            type=EventType.TASK_COMPLETE,
            data={
                "task_id": task.id,
                "duration_s": duration,
                "invocation_summary": tracker.summary(),
            },
        ),
        result_text,
        tracker,
    )


async def execute_with_convergence(
    task_graph: Any,
    model: ModelProtocol,
    cwd: Path,
    naaru: Any,
    options: Any,
    execute_with_gates_fn: Any,
) -> AsyncIterator[AgentEvent]:
    """Execute with convergence loops enabled (RFC-123).

    After each task completes, runs validation gates and fixes errors
    until code stabilizes or limits are reached.

    Args:
        task_graph: The task graph
        model: Model for generation
        cwd: Working directory
        naaru: Naaru instance
        options: Execution options including convergence config
        execute_with_gates_fn: Function to execute with gates

    Yields:
        AgentEvent for each step
    """
    from sunwell.agent.convergence import ConvergenceConfig, ConvergenceLoop

    config = options.convergence_config or ConvergenceConfig()

    # Create convergence loop
    loop = ConvergenceLoop(
        model=model,
        cwd=cwd,
        config=config,
    )

    # Track files written during execution
    written_files: list[Path] = []
    artifacts: dict[str, Artifact] = {}

    async def on_write(path: Path) -> None:
        """Hook called after each file write."""
        written_files.append(path)
        # Build artifact for convergence
        if path.exists():
            artifacts[str(path)] = Artifact(
                path=path,
                content=path.read_text(),
                task_id="convergence",
            )

    # Set up hook on tool executor
    if naaru and naaru.tool_executor:
        naaru.tool_executor.on_file_write = on_write

    try:
        # Execute tasks normally with gates
        async for event in execute_with_gates_fn(options):
            yield event

            # After each task completes, run convergence if files changed
            if event.type == EventType.TASK_COMPLETE and written_files:
                async for conv_event in loop.run(list(written_files), artifacts):
                    yield conv_event

                if loop.result and not loop.result.stable:
                    # Escalate if convergence failed
                    yield AgentEvent(
                        EventType.ESCALATE,
                        {"reason": f"Convergence failed: {loop.result.status.value}"},
                    )
                    return

                written_files.clear()

            if event.type in (EventType.ERROR, EventType.ESCALATE):
                return
    finally:
        # Clean up hook
        if naaru and naaru.tool_executor:
            naaru.tool_executor.on_file_write = None
