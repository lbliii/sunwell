"""Agentic tool loop for S-Tier tool calling.

Implements a proper agentic loop pattern matching Claude Code and OpenAI Agents SDK:
- Model calls tools via native tool calling
- Tool results fed back into conversation
- Loop continues until model responds without tool calls

Sunwell differentiators:
- Confidence-routed execution (Vortex/Interference/Single-shot)
- Learning injection for memory-aware tool calls
- Validation gates after file operations
- Recovery state on failures
- Tool call introspection (RFC-134)
- Automatic retry with strategy escalation (RFC-134)
- Tool usage learning (RFC-134)
- Progressive tool enablement (RFC-134)
- Smart-to-dumb model delegation (RFC-137)
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from sunwell.agent.events import (
    AgentEvent,
    delegation_started_event,
    ephemeral_lens_created_event,
    signal_event,
    tool_complete_event,
    tool_error_event,
    tool_loop_complete_event,
    tool_loop_start_event,
    tool_loop_turn_event,
    tool_start_event,
)
from sunwell.agent.introspection import IntrospectionResult, introspect_tool_call
from sunwell.models.protocol import (
    GenerateOptions,
    GenerateResult,
    Message,
    Tool,
    ToolCall,
)
from sunwell.tools.types import ToolResult

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore
    from sunwell.agent.signals import AdaptiveSignals
    from sunwell.agent.validation import ValidationStage
    from sunwell.core.lens import EphemeralLens, Lens, LensLike
    from sunwell.mirror.handler import MirrorHandler
    from sunwell.models.protocol import ModelProtocol
    from sunwell.recovery.manager import RecoveryManager
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.progressive import ProgressivePolicy
    from sunwell.vortex.primitives import InterferenceResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoopConfig:
    """Configuration for the agentic loop."""

    max_turns: int = 20
    """Maximum turns before stopping (prevents infinite loops)."""

    temperature: float = 0.3
    """Temperature for model generation."""

    tool_choice: Literal["auto", "none", "required"] | str = "auto"
    """Tool choice mode: auto (model decides), none, required, or specific tool name."""

    enable_confidence_routing: bool = True
    """Use confidence-based routing (Vortex/Interference/Single-shot)."""

    enable_learning_injection: bool = True
    """Inject relevant learnings into tool call context."""

    enable_validation_gates: bool = True
    """Run validation gates after file operations."""

    enable_recovery: bool = True
    """Save recovery state on failures."""

    enable_expertise_injection: bool = True
    """Enhance tool descriptions with lens-specific heuristics."""

    enable_self_reflection: bool = True
    """Reflect on tool patterns every N turns and adjust strategy."""

    reflection_interval: int = 5
    """How often to trigger self-reflection (every N turns)."""

    # RFC-134: Tool call introspection
    enable_introspection: bool = True
    """Intercept and repair malformed tool arguments before execution."""

    # RFC-134: Automatic retry with strategy escalation
    enable_strategy_escalation: bool = True
    """Escalate through strategies (single → interference → vortex) on failures."""

    max_retries_per_tool: int = 3
    """Maximum retries per tool call before escalating to user."""

    # RFC-134: Tool usage learning
    enable_tool_learning: bool = True
    """Track which tool sequences succeed for which task types."""

    # RFC-134: Progressive tool enablement
    enable_progressive_tools: bool = False
    """Start with read-only tools and unlock write tools as trust builds."""

    # RFC-137: Smart-to-dumb model delegation
    enable_delegation: bool = False
    """Enable smart-to-dumb model delegation for cost optimization.

    When enabled and delegation criteria are met, the loop will:
    1. Use a smart model to create an EphemeralLens
    2. Execute the task with a cheaper delegation model using the lens
    """

    delegation_threshold_tokens: int = 2000
    """Minimum expected output tokens to trigger delegation.

    Tasks expected to generate more than this many tokens will use
    delegation if enabled. Lower values = more aggressive delegation.
    """


@dataclass(slots=True)
class LoopState:
    """Mutable state for the agentic loop."""

    messages: list[Message] = field(default_factory=list)
    """Conversation history."""

    turn: int = 0
    """Current turn number."""

    tool_calls_total: int = 0
    """Total tool calls executed."""

    file_writes: list[str] = field(default_factory=list)
    """Paths of files written (for validation gates)."""

    # RFC-134: Failure tracking for strategy escalation
    failure_counts: dict[str, int] = field(default_factory=dict)
    """tool_call_id -> failure count for retry escalation."""

    # RFC-134: Tool sequence tracking for learning
    tool_sequence: list[str] = field(default_factory=list)
    """Ordered list of tools called in this turn (for pattern learning)."""

    # RFC-134: Introspection repairs tracking
    repairs_made: int = 0
    """Count of repairs made by introspection."""


@dataclass(slots=True)
class AgentLoop:
    """Agentic tool loop following Claude Code / OpenAI Agents patterns.

    The loop:
    1. Sends task + tools to model
    2. Model returns tool_calls or text
    3. If tool_calls: execute tools, append results, repeat
    4. If text only: return (task complete)

    Sunwell advantages:
    - Confidence-routed: Low confidence uses Vortex (multiple candidates)
    - Learning-aware: Injects past learnings into context
    - Validation-gated: Runs syntax/lint after file writes
    - Recovery-enabled: Saves state on failures for later resume
    - Tool call introspection: Repair malformed arguments (RFC-134)
    - Strategy escalation: Single → Interference → Vortex on failures (RFC-134)
    - Tool learning: Track which sequences work for which tasks (RFC-134)
    - Progressive tools: Unlock tools as trust builds (RFC-134)
    """

    model: ModelProtocol
    executor: ToolExecutor
    config: LoopConfig = field(default_factory=LoopConfig)

    # Workspace for path validation
    workspace: Path | None = None
    """Workspace root for path validation (defaults to executor._resolved_workspace)."""

    # Optional Sunwell integrations (differentiators)
    learning_store: LearningStore | None = None
    validation_stage: ValidationStage | None = None
    recovery_manager: RecoveryManager | None = None
    lens: Lens | None = None
    mirror_handler: MirrorHandler | None = None

    # RFC-134: Progressive tool policy (set during run if enabled)
    progressive_policy: ProgressivePolicy | None = field(default=None, init=False)
    """Dynamic tool availability based on turn/trust (RFC-134)."""

    # RFC-137: Model delegation
    smart_model: ModelProtocol | None = None
    """Smart model for lens creation (delegation)."""

    delegation_model: ModelProtocol | None = None
    """Cheap model for delegated execution (delegation)."""

    # Internal flag to prevent delegation recursion
    _in_delegation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Initialize workspace from executor if not provided."""
        if self.workspace is None and hasattr(self.executor, "_resolved_workspace"):
            self.workspace = self.executor._resolved_workspace
        if self.workspace is None:
            self.workspace = Path.cwd()

    async def run(
        self,
        task_description: str,
        tools: tuple[Tool, ...] | None = None,
        system_prompt: str | None = None,
        context: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the agentic tool loop.

        Args:
            task_description: What to accomplish
            tools: Available tools (defaults to executor's tools)
            system_prompt: Optional system prompt
            context: Additional context (e.g., file contents)

        Yields:
            AgentEvent for progress tracking
        """
        # Get tools from executor if not provided
        if tools is None:
            tools = self.executor.get_tool_definitions()

        # DIFFERENTIATOR: Enhance tools with lens expertise
        tools = self._enhance_tools_with_expertise(tools)

        # RFC-134: Initialize progressive tool policy if enabled
        if self.config.enable_progressive_tools:
            from sunwell.tools.progressive import ProgressivePolicy
            from sunwell.tools.types import ToolTrust

            # Get base trust from executor policy or default to WORKSPACE
            base_trust = ToolTrust.WORKSPACE
            if hasattr(self.executor, "policy") and self.executor.policy:
                base_trust = self.executor.policy.trust_level

            self.progressive_policy = ProgressivePolicy(base_trust=base_trust)
            logger.info(
                "Progressive tools enabled: starting with %d tools",
                len(self.progressive_policy.get_available_tools()),
            )

        # RFC-137: Check if delegation should be used (skip if already in delegation)
        if (
            self.config.enable_delegation
            and self.delegation_model is not None
            and not self._in_delegation
        ):
            from sunwell.agent.ephemeral_lens import should_use_delegation

            # Estimate tokens based on task complexity
            estimated_tokens = self._estimate_output_tokens(task_description)

            if await should_use_delegation(
                task_description,
                estimated_tokens,
                budget_remaining=50_000,  # TODO: Get from budget tracker
            ):
                logger.info(
                    "Delegation triggered: %d estimated tokens > threshold %d",
                    estimated_tokens,
                    self.config.delegation_threshold_tokens,
                )
                async for event in self._run_with_delegation(
                    task_description, tools, system_prompt, context
                ):
                    yield event
                return

        # Initialize state
        state = LoopState()

        # Build initial messages
        if system_prompt:
            state.messages.append(Message(role="system", content=system_prompt))

        # Inject learnings if enabled
        learnings_injected = False
        if self.config.enable_learning_injection and self.learning_store:
            learnings_prompt = await self._get_learnings_prompt(task_description)
            if learnings_prompt:
                state.messages.append(Message(role="system", content=learnings_prompt))
                learnings_injected = True

        # Track what differentiators are active (for observability)
        differentiators_active = []
        if tools != self.executor.get_tool_definitions():
            differentiators_active.append("expertise_injection")
        if learnings_injected:
            differentiators_active.append("learning_injection")
        if self.config.enable_confidence_routing:
            differentiators_active.append("confidence_routing")
        if self.config.enable_validation_gates and self.validation_stage:
            differentiators_active.append("validation_gates")
        if self.config.enable_self_reflection and self.mirror_handler:
            differentiators_active.append("self_reflection")
        if self.config.enable_recovery and self.recovery_manager:
            differentiators_active.append("recovery")
        if self.config.enable_introspection:
            differentiators_active.append("tool_introspection")
        if self.config.enable_strategy_escalation:
            differentiators_active.append("strategy_escalation")
        if self.config.enable_tool_learning:
            differentiators_active.append("tool_learning")
        if self.config.enable_progressive_tools:
            differentiators_active.append("progressive_tools")

        # Emit differentiators event if any are active
        if differentiators_active:
            yield signal_event(
                "differentiators_active",
                differentiators=differentiators_active,
                count=len(differentiators_active),
            )

        # Build user message with context
        user_content = task_description
        if context:
            user_content = f"{context}\n\n{task_description}"
        state.messages.append(Message(role="user", content=user_content))

        # Emit loop start
        yield tool_loop_start_event(
            task_description=task_description,
            max_turns=self.config.max_turns,
            tool_count=len(tools),
        )

        # Main loop
        final_response: str | None = None
        while state.turn < self.config.max_turns:
            state.turn += 1

            # RFC-134: Advance progressive policy turn
            if self.progressive_policy:
                self.progressive_policy.advance_turn()

            # RFC-134: Filter tools based on progressive policy
            available_tools = tools
            if self.progressive_policy:
                available_tools = self.progressive_policy.filter_tools(tools)
                if len(available_tools) != len(tools):
                    logger.debug(
                        "Progressive tools: %d/%d tools available at turn %d",
                        len(available_tools),
                        len(tools),
                        state.turn,
                    )

            # Generate with tools (first turn uses task_description for routing)
            routing_task = task_description if state.turn == 1 else None
            result = await self._generate_with_routing(
                state.messages,
                available_tools,
                task_description=routing_task,
            )

            if result.has_tool_calls:
                yield tool_loop_turn_event(
                    turn=state.turn,
                    tool_calls_count=len(result.tool_calls),
                )

                # Execute tool calls
                async for event in self._execute_tool_calls(
                    result.tool_calls,
                    state,
                ):
                    yield event

                # DIFFERENTIATOR: Self-reflection every N turns
                if (
                    self.config.enable_self_reflection
                    and self.mirror_handler
                    and state.turn % self.config.reflection_interval == 0
                ):
                    async for event in self._run_self_reflection(state, task_description):
                        yield event

            else:
                # No tool calls = done
                final_response = result.text
                break

        # Emit loop complete
        yield tool_loop_complete_event(
            turns_used=state.turn,
            tool_calls_total=state.tool_calls_total,
            final_response=final_response,
        )

        # Run validation gates if enabled and files were written
        validation_passed = True
        if (
            self.config.enable_validation_gates
            and self.validation_stage
            and state.file_writes
        ):
            async for event in self._run_validation_gates(state.file_writes):
                yield event
                # Track if validation failed
                if event.type.value in ("gate_fail", "validate_error"):
                    validation_passed = False

        # RFC-134: Update progressive policy with validation outcome
        if self.progressive_policy:
            if validation_passed and state.file_writes:
                self.progressive_policy.record_validation_pass()
                logger.debug(
                    "Progressive policy: validation passed, %d passes total",
                    self.progressive_policy.validation_passes,
                )
            elif not validation_passed:
                self.progressive_policy.record_validation_failure()
                logger.debug(
                    "Progressive policy: validation failed, %d failures total",
                    self.progressive_policy.validation_failures,
                )

        # RFC-134: Record tool sequence for learning
        if (
            self.config.enable_tool_learning
            and self.learning_store
            and state.tool_sequence
        ):
            from sunwell.agent.learning import classify_task_type

            task_type = classify_task_type(task_description)
            # Consider success if we got a final response and validation passed
            success = final_response is not None and validation_passed
            self.learning_store.record_tool_sequence(
                task_type=task_type,
                tools=state.tool_sequence,
                success=success,
            )
            logger.debug(
                "Recorded tool sequence: %s -> %s (success=%s)",
                task_type,
                state.tool_sequence,
                success,
            )

    async def _generate_with_routing(
        self,
        messages: list[Message],
        tools: tuple[Tool, ...],
        task_description: str | None = None,
    ) -> GenerateResult:
        """Generate with optional confidence-based routing.

        High confidence (>0.85): Single-shot
        Medium confidence (0.6-0.85): Interference (3 perspectives)
        Low confidence (<0.6): Vortex (multiple candidates, pick best)

        This is a KEY DIFFERENTIATOR - competitors always use single-shot.
        """
        options = GenerateOptions(
            temperature=self.config.temperature,
        )

        # Skip routing if disabled
        if not self.config.enable_confidence_routing:
            return await self._single_shot_generate(messages, tools, options)

        # Extract confidence if we have task description
        confidence = await self._get_task_confidence(task_description, messages)

        # Route based on confidence
        if confidence < 0.6:
            # Low confidence → Vortex (multiple candidates)
            strategy = "vortex"
            logger.info(
                "◎ CONFIDENCE ROUTING → Vortex (multiple candidates) [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": strategy},
            )
            return await self._vortex_generate(messages, tools, options)
        elif confidence < 0.85:
            # Medium confidence → Interference (3 perspectives)
            strategy = "interference"
            logger.info(
                "◎ CONFIDENCE ROUTING → Interference (3 perspectives) [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": strategy},
            )
            return await self._interference_generate(messages, tools, options)
        else:
            # High confidence → Single-shot
            strategy = "single_shot"
            logger.info(
                "◎ CONFIDENCE ROUTING → Single-shot [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": strategy},
            )
            return await self._single_shot_generate(messages, tools, options)

    async def _get_task_confidence(
        self,
        task_description: str | None,
        messages: list[Message],
    ) -> float:
        """Extract confidence for routing decisions.

        Uses signals extraction if available, otherwise defaults to high confidence.
        """
        if not task_description:
            # Extract from last user message
            for msg in reversed(messages):
                if msg.role == "user" and msg.content:
                    task_description = msg.content
                    break

        if not task_description:
            return 0.9  # Default to high confidence if no task

        try:
            from sunwell.agent.signals import extract_signals

            signals = await extract_signals(task_description, self.model)
            return signals.effective_confidence
        except Exception:
            # If signal extraction fails, default to high confidence
            return 0.9

    async def _single_shot_generate(
        self,
        messages: list[Message],
        tools: tuple[Tool, ...],
        options: GenerateOptions,
    ) -> GenerateResult:
        """Standard single-shot generation."""
        return await self.model.generate(
            tuple(messages),
            tools=tools,
            tool_choice=self.config.tool_choice,
            options=options,
        )

    async def _interference_generate(
        self,
        messages: list[Message],
        tools: tuple[Tool, ...],
        options: GenerateOptions,
    ) -> GenerateResult:
        """Generate with 3 perspectives and pick best (interference pattern).

        Like constructive/destructive interference in physics:
        - High agreement = constructive (amplified confidence in result)
        - Low agreement = destructive (signals uncertainty)
        """
        perspectives = ["analyst", "pragmatist", "expert"]
        candidates: list[GenerateResult] = []

        for perspective in perspectives:
            # Add perspective hint to system
            perspective_messages = list(messages)
            if perspective_messages and perspective_messages[0].role == "system":
                # Prepend to existing system prompt
                old_content = perspective_messages[0].content or ""
                perspective_messages[0] = Message(
                    role="system",
                    content=f"[Perspective: {perspective}] {old_content}",
                )
            else:
                # Insert new system message
                perspective_messages.insert(0, Message(
                    role="system",
                    content=f"Think from the perspective of a {perspective}.",
                ))

            try:
                result = await self.model.generate(
                    tuple(perspective_messages),
                    tools=tools,
                    tool_choice=self.config.tool_choice,
                    options=options,
                )
                candidates.append(result)
            except Exception:
                continue

        if not candidates:
            # All failed, fall back to single-shot
            return await self._single_shot_generate(messages, tools, options)

        # Select best candidate via voting/agreement
        return self._select_best_candidate(candidates)

    async def _vortex_generate(
        self,
        messages: list[Message],
        tools: tuple[Tool, ...],
        options: GenerateOptions,
    ) -> GenerateResult:
        """Generate multiple candidates with different temperatures (Vortex).

        For low-confidence tasks, explore the solution space more thoroughly.
        """
        temperatures = [0.2, 0.5, 0.8]
        candidates: list[GenerateResult] = []

        for temp in temperatures:
            varied_options = GenerateOptions(
                temperature=temp,
                max_tokens=options.max_tokens,
                stop_sequences=options.stop_sequences,
            )

            try:
                result = await self.model.generate(
                    tuple(messages),
                    tools=tools,
                    tool_choice=self.config.tool_choice,
                    options=varied_options,
                )
                candidates.append(result)
            except Exception:
                continue

        if not candidates:
            return await self._single_shot_generate(messages, tools, options)

        return self._select_best_candidate(candidates)

    def _select_best_candidate(self, candidates: list[GenerateResult]) -> GenerateResult:
        """Select the best candidate from multiple generations.

        Preferences:
        1. Candidates with tool calls (actionable)
        2. Candidates with more tool calls (more complete)
        3. First candidate if tied
        """
        if not candidates:
            raise ValueError("No candidates to select from")

        # Prefer candidates with tool calls
        with_tools = [c for c in candidates if c.has_tool_calls]
        if with_tools:
            # Pick the one with most tool calls
            return max(with_tools, key=lambda c: len(c.tool_calls))

        # No tool calls - return first (most deterministic temperature)
        return candidates[0]

    async def _execute_tool_calls(
        self,
        tool_calls: tuple[ToolCall, ...],
        state: LoopState,
    ) -> AsyncIterator[AgentEvent]:
        """Execute tool calls and update state.

        RFC-134: Includes introspection for argument validation/repair
        and retry escalation on failures.
        """
        for tc in tool_calls:
            # RFC-134: Pre-execution introspection
            if self.config.enable_introspection:
                introspection = introspect_tool_call(tc, self.workspace)

                # Handle blocked calls
                if introspection.blocked:
                    logger.warning(
                        "Tool call blocked by introspection: %s - %s",
                        tc.name,
                        introspection.block_reason,
                    )
                    yield tool_error_event(
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                        error=f"Blocked: {introspection.block_reason}",
                    )
                    # Append error as tool result for conversation continuity
                    state.messages.append(Message(
                        role="assistant",
                        tool_calls=(tc,),
                    ))
                    state.messages.append(Message(
                        role="tool",
                        content=f"Error: {introspection.block_reason}",
                        tool_call_id=tc.id,
                    ))
                    continue

                # Log repairs made
                if introspection.repairs:
                    state.repairs_made += len(introspection.repairs)
                    for repair in introspection.repairs:
                        logger.info("Introspection repair: %s", repair)

                # Log warnings
                for warning in introspection.warnings:
                    logger.warning("Introspection warning: %s", warning)

                # Use repaired tool call
                tc = introspection.tool_call

            # Emit tool start
            yield tool_start_event(
                tool_name=tc.name,
                tool_call_id=tc.id,
                arguments=tc.arguments,
            )

            # RFC-134: Track tool sequence for learning
            state.tool_sequence.append(tc.name)

            # Execute tool with retry escalation support
            async for event in self._execute_single_tool(tc, state):
                yield event

    async def _execute_single_tool(
        self,
        tc: ToolCall,
        state: LoopState,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a single tool with retry escalation on failure (RFC-134).

        Escalation ladder:
        - Failure 1: Retry same approach
        - Failure 2: Interference (3 perspectives)
        - Failure 3: Vortex (multiple candidates)
        - Failure 4+: Record dead-end, escalate to user
        """
        try:
            result = await self.executor.execute(tc)
            state.tool_calls_total += 1

            # Track file writes for validation gates
            if tc.name in ("write_file", "edit_file") and result.success:
                path = tc.arguments.get("path", "")
                if path:
                    state.file_writes.append(path)

            # Emit tool complete
            yield tool_complete_event(
                tool_name=tc.name,
                tool_call_id=tc.id,
                success=result.success,
                output=result.output,
                execution_time_ms=result.execution_time_ms or 0,
            )

            # Append messages for conversation
            state.messages.append(Message(
                role="assistant",
                tool_calls=(tc,),
            ))
            state.messages.append(Message(
                role="tool",
                content=result.output,
                tool_call_id=tc.id,
            ))

            # Clear failure count on success
            if result.success and tc.id in state.failure_counts:
                del state.failure_counts[tc.id]

        except Exception as e:
            logger.exception("Tool execution failed: %s", tc.name)
            error_msg = str(e)

            # RFC-134: Track failure for escalation
            failure_count = state.failure_counts.get(tc.id, 0) + 1
            state.failure_counts[tc.id] = failure_count

            # RFC-134: Attempt retry with strategy escalation
            if self.config.enable_strategy_escalation:
                if failure_count <= self.config.max_retries_per_tool:
                    logger.info(
                        "Retry escalation: attempt %d/%d for %s",
                        failure_count,
                        self.config.max_retries_per_tool,
                        tc.name,
                    )
                    async for event in self._retry_with_escalation(
                        tc, error_msg, failure_count, state
                    ):
                        yield event
                    return

            # No escalation or max retries exceeded
            yield tool_error_event(
                tool_name=tc.name,
                tool_call_id=tc.id,
                error=error_msg,
            )

            # Append error as tool result
            state.messages.append(Message(
                role="assistant",
                tool_calls=(tc,),
            ))
            state.messages.append(Message(
                role="tool",
                content=f"Error: {error_msg}",
                tool_call_id=tc.id,
            ))

            # Save recovery state if enabled
            if self.config.enable_recovery and self.recovery_manager:
                await self._save_recovery_state(tc, error_msg, state)

    async def _retry_with_escalation(
        self,
        tc: ToolCall,
        error: str,
        failure_count: int,
        state: LoopState,
    ) -> AsyncIterator[AgentEvent]:
        """Retry tool call with strategy escalation (RFC-134).

        Escalation ladder:
        - Failure 1: Simple retry (maybe transient error)
        - Failure 2: Interference (3 perspectives on the fix)
        - Failure 3: Vortex (multiple candidate fixes)
        - Failure 4+: Record dead-end and escalate to user
        """
        if failure_count == 1:
            # Simple retry - maybe transient error
            logger.info("Strategy: Simple retry for %s", tc.name)
            async for event in self._execute_single_tool(tc, state):
                yield event

        elif failure_count == 2:
            # Interference: 3 perspectives on fixing the error
            logger.info("Strategy: Interference (3 perspectives) for %s", tc.name)
            fixed_tc = await self._interference_fix(tc, error, state)
            if fixed_tc:
                async for event in self._execute_single_tool(fixed_tc, state):
                    yield event
            else:
                # Interference failed to produce fix, fall through to error
                yield tool_error_event(
                    tool_name=tc.name,
                    tool_call_id=tc.id,
                    error=f"Interference fix failed: {error}",
                )

        elif failure_count == 3:
            # Vortex: multiple candidate fixes
            logger.info("Strategy: Vortex (multiple candidates) for %s", tc.name)
            fixed_tc = await self._vortex_fix(tc, error, state)
            if fixed_tc:
                async for event in self._execute_single_tool(fixed_tc, state):
                    yield event
            else:
                yield tool_error_event(
                    tool_name=tc.name,
                    tool_call_id=tc.id,
                    error=f"Vortex fix failed: {error}",
                )

        else:
            # Max retries exceeded - record dead-end and escalate
            logger.warning(
                "Max retries exceeded for %s, recording dead-end",
                tc.name,
            )
            await self._record_tool_dead_end(tc, error)
            yield tool_error_event(
                tool_name=tc.name,
                tool_call_id=tc.id,
                error=f"Max retries exceeded after {failure_count} attempts: {error}",
            )

    async def _interference_fix(
        self,
        tc: ToolCall,
        error: str,
        state: LoopState,
    ) -> ToolCall | None:
        """Use interference (3 perspectives) to fix a failed tool call.

        Returns a repaired ToolCall or None if fix failed.
        """
        fix_prompt = f"""A tool call failed. Analyze from 3 perspectives and fix it.

Tool: {tc.name}
Arguments: {tc.arguments}
Error: {error}

Provide the corrected arguments as a JSON object."""

        # Use interference generate to get multiple perspectives
        messages = [Message(role="user", content=fix_prompt)]
        options = GenerateOptions(temperature=0.5, max_tokens=500)

        try:
            result = await self._interference_generate(
                messages,
                tools=(),  # No tools, just get JSON response
                options=options,
            )

            if result.text:
                import json
                # Try to parse JSON from response
                try:
                    # Extract JSON from response
                    text = result.text.strip()
                    if "```" in text:
                        # Extract from code block
                        import re
                        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                        if match:
                            text = match.group(1)
                    fixed_args = json.loads(text)
                    return ToolCall(id=tc.id, name=tc.name, arguments=fixed_args)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse interference fix as JSON")
                    return None
        except Exception as e:
            logger.warning("Interference fix failed: %s", e)
            return None

        return None

    async def _vortex_fix(
        self,
        tc: ToolCall,
        error: str,
        state: LoopState,
    ) -> ToolCall | None:
        """Use vortex (multiple candidates) to fix a failed tool call.

        Returns a repaired ToolCall or None if fix failed.
        """
        fix_prompt = f"""A tool call failed. Generate the best fix.

Tool: {tc.name}
Arguments: {tc.arguments}
Error: {error}

Provide the corrected arguments as a JSON object."""

        messages = [Message(role="user", content=fix_prompt)]
        options = GenerateOptions(temperature=0.3, max_tokens=500)

        try:
            result = await self._vortex_generate(
                messages,
                tools=(),
                options=options,
            )

            if result.text:
                import json
                try:
                    text = result.text.strip()
                    if "```" in text:
                        import re
                        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                        if match:
                            text = match.group(1)
                    fixed_args = json.loads(text)
                    return ToolCall(id=tc.id, name=tc.name, arguments=fixed_args)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse vortex fix as JSON")
                    return None
        except Exception as e:
            logger.warning("Vortex fix failed: %s", e)
            return None

        return None

    async def _record_tool_dead_end(self, tc: ToolCall, error: str) -> None:
        """Record a tool call failure as a dead-end for future avoidance.

        RFC-134: Dead-ends are stored in LearningStore and can be used
        to avoid similar failures in future sessions.
        """
        if not self.learning_store:
            return

        from sunwell.agent.learning import DeadEnd

        dead_end = DeadEnd(
            approach=f"Tool {tc.name} with args: {tc.arguments}",
            reason=error,
            context=f"Failed after {self.config.max_retries_per_tool} retries",
        )
        self.learning_store.add_dead_end(dead_end)
        logger.info("Recorded dead-end: %s", dead_end.approach[:100])

    async def _get_learnings_prompt(self, task_description: str) -> str | None:
        """Get relevant learnings and tool suggestions for the task (RFC-134)."""
        if not self.learning_store:
            return None

        try:
            sections: list[str] = []

            # Get relevant learnings
            relevant = self.learning_store.get_relevant(task_description)
            if relevant:
                learnings_text = "\n".join(f"- {l.fact}" for l in relevant[:5])
                sections.append(f"Apply these known facts from past experience:\n{learnings_text}")
                logger.info(
                    "Learning injection: Applied %d learnings from memory",
                    len(relevant[:5]),
                    extra={"learnings_count": len(relevant[:5])},
                )

            # RFC-134: Get tool suggestions based on task type
            if self.config.enable_tool_learning:
                from sunwell.agent.learning import classify_task_type

                task_type = classify_task_type(task_description)
                tool_suggestion = self.learning_store.format_tool_suggestions(task_type)
                if tool_suggestion:
                    sections.append(tool_suggestion)
                    logger.info(
                        "Tool suggestion: %s for task type '%s'",
                        tool_suggestion,
                        task_type,
                    )

            return "\n\n".join(sections) if sections else None

        except Exception as e:
            logger.warning("Failed to get learnings: %s", e)
            return None

    async def _run_validation_gates(
        self,
        file_paths: list[str],
    ) -> AsyncIterator[AgentEvent]:
        """Run validation gates on written files (Sunwell differentiator).

        After each file write, runs syntax/lint validation. This catches
        errors early before they propagate - competitors don't do this.
        """
        if not self.validation_stage:
            logger.debug("Validation gates skipped - no validation stage configured")
            return

        logger.info(
            "═ VALIDATION GATES → Running syntax/lint on %d file(s)",
            len(file_paths),
            extra={"files": file_paths},
        )

        from sunwell.agent.events import gate_start_event, gate_step_event, EventType
        from sunwell.agent.validation import Artifact

        # Create artifacts for validation
        artifacts = [
            Artifact(path=path, content="")  # Content loaded by validator
            for path in file_paths
        ]

        # Create validation gate for post-write checks
        from sunwell.agent.gates import ValidationGate

        gate = ValidationGate(
            id="post_tool_write",
            type="syntax",  # Start with syntax, can expand
            after_tasks=[],
        )

        # Emit gate start
        yield gate_start_event(
            gate_id=gate.id,
            gate_type="syntax",
            artifacts=[a.path for a in artifacts],
        )

        try:
            # Run validation
            gate_result = await self.validation_stage.run_gate(gate, artifacts)

            # Emit step events
            for step_result in gate_result.step_results:
                yield gate_step_event(
                    gate_id=gate.id,
                    step=step_result.step,
                    passed=step_result.passed,
                    message=step_result.message or "",
                )

            # If validation failed, emit error events
            if not gate_result.passed:
                from sunwell.agent.events import validate_error_event

                for error in gate_result.errors:
                    yield validate_error_event(
                        error_type="validation",
                        message=str(error),
                        file=error.file if hasattr(error, "file") else None,
                        line=error.line if hasattr(error, "line") else None,
                    )

                # Log for telemetry
                logger.warning(
                    "Validation gate failed after tool write",
                    extra={
                        "files": file_paths,
                        "errors": len(gate_result.errors),
                    },
                )

        except Exception as e:
            logger.warning("Validation gate error: %s", e)
            # Don't fail the entire operation if validation has issues

    async def _save_recovery_state(
        self,
        failed_tool: ToolCall,
        error: str,
        state: LoopState,
    ) -> None:
        """Save recovery state for later resume (Sunwell differentiator).

        When tool execution fails, we save the current state so the user can:
        - Review what happened with `sunwell review`
        - Resume from where they left off
        - Manually fix and continue

        Competitors lose all progress on failure - Sunwell preserves it.
        """
        if not self.recovery_manager:
            logger.debug("Recovery skipped - no recovery manager configured")
            return

        try:
            from sunwell.recovery.types import RecoveryState

            # Build context from messages
            conversation_context = []
            for msg in state.messages[-10:]:  # Last 10 messages
                role = msg.role
                content = msg.content[:500] if msg.content else ""
                conversation_context.append(f"[{role}] {content}")

            # Extract goal from first user message
            goal = ""
            for msg in state.messages:
                if msg.role == "user" and msg.content:
                    goal = msg.content[:200]
                    break

            # Create recovery state
            recovery_state = RecoveryState(
                goal=goal,
                artifacts=state.file_writes,
                failed_gate="tool_execution",
                error_details=[
                    f"Tool: {failed_tool.name}",
                    f"Arguments: {failed_tool.arguments}",
                    f"Error: {error}",
                ],
                context={
                    "turn": state.turn,
                    "tool_calls_total": state.tool_calls_total,
                    "conversation": conversation_context,
                },
            )

            # Save via recovery manager
            await self.recovery_manager.save(recovery_state)

            logger.info(
                "◇ RECOVERY → State saved [sunwell review to resume]",
                extra={
                    "tool": failed_tool.name,
                    "turn": state.turn,
                    "files_written": len(state.file_writes),
                },
            )

        except Exception as e:
            logger.warning("Failed to save recovery state: %s", e)
            # Don't fail the operation if recovery save fails

    def _enhance_tools_with_expertise(
        self,
        tools: tuple[Tool, ...],
    ) -> tuple[Tool, ...]:
        """Enhance tool descriptions with lens-specific heuristics (Sunwell differentiator).

        Dynamically injects domain expertise into tool descriptions so the model
        knows HOW to use tools correctly for this domain. Competitors use static
        tool descriptions - Sunwell's tools are context-aware.

        Example:
            write_file for Python lens gets:
            "When writing Python files: always include type hints, use snake_case,
             add docstrings to public functions. AVOID: global state, print debugging."
        """
        if not self.lens or not self.config.enable_expertise_injection:
            return tools

        try:
            # Extract heuristics from lens
            heuristics: list[str] = []
            anti_heuristics: list[str] = []

            # Get heuristics (do's)
            if hasattr(self.lens, "heuristics"):
                for h in self.lens.heuristics[:5]:  # Limit to top 5
                    if hasattr(h, "name") and hasattr(h, "description"):
                        heuristics.append(f"{h.name}: {h.description}")
                    elif hasattr(h, "content"):
                        heuristics.append(str(h.content)[:100])
                    else:
                        heuristics.append(str(h)[:100])

            # Get anti-heuristics (don'ts)
            if hasattr(self.lens, "anti_heuristics"):
                for ah in self.lens.anti_heuristics[:3]:  # Limit to top 3
                    if hasattr(ah, "pattern"):
                        anti_heuristics.append(f"AVOID: {ah.pattern}")
                    else:
                        anti_heuristics.append(f"AVOID: {str(ah)[:80]}")

            if not heuristics and not anti_heuristics:
                return tools

            # Build expertise suffix for file-writing tools
            expertise_suffix = ""
            if heuristics:
                expertise_suffix += " BEST PRACTICES: " + "; ".join(heuristics[:3])
            if anti_heuristics:
                expertise_suffix += " " + "; ".join(anti_heuristics[:2])

            # Enhance write_file and edit_file descriptions
            enhanced: list[Tool] = []
            for tool in tools:
                if tool.name in ("write_file", "edit_file"):
                    # Create enhanced copy
                    enhanced.append(Tool(
                        name=tool.name,
                        description=tool.description + expertise_suffix,
                        parameters=tool.parameters,
                    ))
                else:
                    enhanced.append(tool)

            lens_name = "unknown"
            if hasattr(self.lens, "metadata") and hasattr(self.lens.metadata, "name"):
                lens_name = self.lens.metadata.name
            logger.info(
                "⚙ EXPERTISE INJECTION → Enhanced tools with %d heuristics [%s]",
                len(heuristics),
                lens_name,
                extra={
                    "lens": lens_name,
                    "heuristics_count": len(heuristics),
                    "anti_heuristics_count": len(anti_heuristics),
                },
            )

            return tuple(enhanced)

        except Exception as e:
            logger.warning("Failed to enhance tools with expertise: %s", e)
            return tools

    async def _run_self_reflection(
        self,
        state: LoopState,
        task_description: str,
    ) -> AsyncIterator[AgentEvent]:
        """Self-reflect on tool usage patterns and adjust strategy (Sunwell differentiator).

        Every N turns, analyze recent tool calls to detect:
        - Repeated failures → suggest different approach
        - Inefficient patterns → suggest better tool sequence
        - Stuck loops → recommend breaking out

        Competitors blindly continue. Sunwell adapts mid-execution.
        """
        if not self.config.enable_self_reflection:
            return

        if not self.mirror_handler:
            logger.debug("Self-reflection skipped - no mirror handler configured")
            return

        try:
            # Analyze recent tool calls
            analysis = await self.mirror_handler.handle(
                "analyze_patterns",
                {
                    "context": "tool_calls",
                    "scope": "session",
                    "include_sequences": True,
                },
            )

            if not analysis or not analysis.get("patterns"):
                return

            patterns = analysis.get("patterns", [])
            suggestions: list[str] = []

            # Check for repeated failures
            failure_count = sum(1 for p in patterns if p.get("type") == "failure")
            if failure_count >= 2:
                suggestions.append("Multiple failures detected. Consider different approach.")

            # Check for repetitive sequences (stuck in loop)
            sequences = analysis.get("sequences", [])
            for seq in sequences:
                if seq.get("count", 0) >= 3:
                    tool_pair = seq.get("sequence", [])
                    suggestions.append(
                        f"Repetitive pattern detected: {' → '.join(tool_pair)}. "
                        "Breaking may be needed."
                    )

            # Emit reflection event if we have suggestions
            if suggestions:
                yield signal_event(
                    "self_reflection",
                    {
                        "turn": state.turn,
                        "suggestions": suggestions,
                        "patterns_analyzed": len(patterns),
                    },
                )

                # Inject reflection into conversation for model awareness
                reflection_msg = (
                    f"[Self-Reflection at turn {state.turn}] "
                    f"Observed: {'; '.join(suggestions)} "
                    "Consider adjusting approach."
                )
                state.messages.append(Message(role="system", content=reflection_msg))

                logger.info(
                    "◜ SELF-REFLECTION → Detected patterns, suggesting adjustments",
                    extra={
                        "turn": state.turn,
                        "suggestions_count": len(suggestions),
                        "suggestions": suggestions,
                    },
                )

        except Exception as e:
            logger.debug("Self-reflection failed (non-fatal): %s", e)
            # Self-reflection is enhancement, not critical path

    def _estimate_output_tokens(self, task_description: str) -> int:
        """Estimate expected output tokens based on task description.

        Uses simple heuristics to estimate output size. More sophisticated
        estimation could use a classifier or historical data.

        Args:
            task_description: The task to estimate

        Returns:
            Estimated token count for the task output
        """
        # Base estimate: longer descriptions usually mean more complex tasks
        word_count = len(task_description.split())
        base_tokens = word_count * 10  # Rough multiplier

        # Indicators of larger output
        large_indicators = (
            "multiple files",
            "all endpoints",
            "full implementation",
            "complete",
            "crud",
            "scaffold",
            "generate",
        )
        for indicator in large_indicators:
            if indicator in task_description.lower():
                base_tokens *= 2
                break

        # Cap at reasonable range
        return max(500, min(base_tokens, 20_000))

    async def _run_with_delegation(
        self,
        task_description: str,
        tools: tuple[Tool, ...],
        system_prompt: str | None = None,
        context: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute task with smart-to-dumb delegation (RFC-137).

        Uses a smart model to create an EphemeralLens, then executes
        with a cheaper model using that lens for guidance.

        Args:
            task_description: What to accomplish
            tools: Available tools
            system_prompt: Optional system prompt
            context: Additional context

        Yields:
            AgentEvent for progress tracking
        """
        from sunwell.agent.ephemeral_lens import create_ephemeral_lens

        # Must have both smart and delegation models
        if self.smart_model is None:
            self.smart_model = self.model  # Use primary as smart model
        if self.delegation_model is None:
            logger.warning("Delegation requested but no delegation_model set")
            # Fall through to normal execution
            async for event in self.run(task_description, tools, system_prompt, context):
                yield event
            return

        smart_model_id = getattr(self.smart_model, "model_id", "unknown")
        delegation_model_id = getattr(self.delegation_model, "model_id", "unknown")

        # Emit delegation started event
        yield delegation_started_event(
            task_description=task_description,
            smart_model=smart_model_id,
            delegation_model=delegation_model_id,
            reason="Task exceeds delegation threshold",
            estimated_tokens=self._estimate_output_tokens(task_description),
        )

        logger.info(
            "◈ DELEGATION → Creating lens with %s for execution by %s",
            smart_model_id,
            delegation_model_id,
        )

        # Create ephemeral lens using smart model
        context_summary = context[:2000] if context else ""
        ephemeral_lens = await create_ephemeral_lens(
            model=self.smart_model,
            task=task_description,
            context=context_summary,
        )

        # Emit lens created event
        yield ephemeral_lens_created_event(
            task_scope=ephemeral_lens.task_scope,
            heuristics_count=len(ephemeral_lens.heuristics),
            patterns_count=len(ephemeral_lens.patterns),
            anti_patterns_count=len(ephemeral_lens.anti_patterns),
            constraints_count=len(ephemeral_lens.constraints),
            generated_by=ephemeral_lens.generated_by,
        )

        logger.info(
            "◐ LENS CREATED → %s: %d heuristics, %d patterns",
            ephemeral_lens.task_scope[:50],
            len(ephemeral_lens.heuristics),
            len(ephemeral_lens.patterns),
        )

        # Store original model and lens
        original_model = self.model
        original_lens = self.lens

        # Switch to delegation model and ephemeral lens
        self.model = self.delegation_model
        self.lens = ephemeral_lens  # type: ignore[assignment]  # LensLike union

        # Inject lens context into system prompt
        lens_context = ephemeral_lens.to_context()
        enhanced_system = system_prompt or ""
        if lens_context:
            enhanced_system = f"{lens_context}\n\n{enhanced_system}" if enhanced_system else lens_context

        try:
            # Set flag to prevent recursion
            self._in_delegation = True

            # Run the loop with delegation model
            async for event in self.run(
                task_description=task_description,
                tools=tools,
                system_prompt=enhanced_system,
                context=context,
            ):
                yield event

        finally:
            # Restore original model and lens
            self.model = original_model
            self.lens = original_lens
            self._in_delegation = False


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_tool_loop(
    model: ModelProtocol,
    executor: ToolExecutor,
    task_description: str,
    *,
    tools: tuple[Tool, ...] | None = None,
    system_prompt: str | None = None,
    context: str | None = None,
    max_turns: int = 20,
    learning_store: LearningStore | None = None,
) -> AsyncIterator[AgentEvent]:
    """Convenience function to run an agentic tool loop.

    Args:
        model: The model to use
        executor: Tool executor
        task_description: What to accomplish
        tools: Available tools (defaults to executor's tools)
        system_prompt: Optional system prompt
        context: Additional context
        max_turns: Maximum turns
        learning_store: Optional learning store for context injection

    Yields:
        AgentEvent for progress tracking
    """
    loop = AgentLoop(
        model=model,
        executor=executor,
        config=LoopConfig(max_turns=max_turns),
        learning_store=learning_store,
    )

    async for event in loop.run(
        task_description=task_description,
        tools=tools,
        system_prompt=system_prompt,
        context=context,
    ):
        yield event
