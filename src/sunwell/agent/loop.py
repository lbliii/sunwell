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
from typing import TYPE_CHECKING

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
from sunwell.agent.introspection import introspect_tool_call
from sunwell.agent.loop_config import LoopConfig, LoopState
from sunwell.agent.loop_retry import interference_fix, record_tool_dead_end, vortex_fix
from sunwell.agent.loop_routing import (
    estimate_output_tokens,
    get_task_confidence,
    interference_generate,
    single_shot_generate,
    vortex_generate,
)
from sunwell.agent.loop import (
    delegation as loop_delegation,
    expertise as loop_expertise,
    learning as loop_learning,
    recovery as loop_recovery,
    reflection as loop_reflection,
    validation as loop_validation,
)
from sunwell.models.protocol import GenerateOptions, GenerateResult, Message, Tool, ToolCall

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore
    from sunwell.agent.validation import ValidationStage
    from sunwell.foundation.core.lens import Lens
    from sunwell.features.mirror.handler import MirrorHandler
    from sunwell.models.protocol import ModelProtocol
    from sunwell.agent.recovery.manager import RecoveryManager
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.progressive import ProgressivePolicy

logger = logging.getLogger(__name__)


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
        tools = loop_expertise.enhance_tools_with_expertise(
            tools, self.lens, self.config.enable_expertise_injection
        )

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
                async for event in loop_delegation.run_with_delegation(
                    self,  # Pass self for model/lens switching
                    task_description,
                    tools,
                    system_prompt,
                    context,
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
            learnings_prompt = await loop_learning.get_learnings_prompt(
                task_description,
                self.learning_store,
                self.config.enable_tool_learning,
            )
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
                    async for event in loop_reflection.run_self_reflection(
                        state, task_description, self.mirror_handler, self.config.reflection_interval
                    ):
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
            async for event in loop_validation.run_validation_gates(
                state.file_writes, self.validation_stage
            ):
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
        options = GenerateOptions(temperature=self.config.temperature)

        # Skip routing if disabled
        if not self.config.enable_confidence_routing:
            return await single_shot_generate(
                self.model, messages, tools, self.config.tool_choice, options
            )

        # Extract confidence if we have task description
        confidence = await get_task_confidence(self.model, task_description, messages)

        # Route based on confidence
        if confidence < 0.6:
            # Low confidence → Vortex (multiple candidates)
            logger.info(
                "◎ CONFIDENCE ROUTING → Vortex (multiple candidates) [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": "vortex"},
            )
            return await vortex_generate(
                self.model, messages, tools, self.config.tool_choice, options
            )
        elif confidence < 0.85:
            # Medium confidence → Interference (3 perspectives)
            logger.info(
                "◎ CONFIDENCE ROUTING → Interference (3 perspectives) [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": "interference"},
            )
            return await interference_generate(
                self.model, messages, tools, self.config.tool_choice, options
            )
        else:
            # High confidence → Single-shot
            logger.info(
                "◎ CONFIDENCE ROUTING → Single-shot [%.2f]",
                confidence,
                extra={"confidence": confidence, "strategy": "single_shot"},
            )
            return await single_shot_generate(
                self.model, messages, tools, self.config.tool_choice, options
            )

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
            escalate = (
                self.config.enable_strategy_escalation
                and failure_count <= self.config.max_retries_per_tool
            )
            if escalate:
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
                await loop_recovery.save_recovery_state(
                    tc, error_msg, state, self.recovery_manager
                )

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
            fixed_tc = await interference_fix(self.model, tc, error, self.config.tool_choice)
            if fixed_tc:
                async for event in self._execute_single_tool(fixed_tc, state):
                    yield event
            else:
                yield tool_error_event(
                    tool_name=tc.name,
                    tool_call_id=tc.id,
                    error=f"Interference fix failed: {error}",
                )

        elif failure_count == 3:
            # Vortex: multiple candidate fixes
            logger.info("Strategy: Vortex (multiple candidates) for %s", tc.name)
            fixed_tc = await vortex_fix(self.model, tc, error, self.config.tool_choice)
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
            logger.warning("Max retries exceeded for %s, recording dead-end", tc.name)
            await record_tool_dead_end(
                self.learning_store, tc, error, self.config.max_retries_per_tool
            )
            yield tool_error_event(
                tool_name=tc.name,
                tool_call_id=tc.id,
                error=f"Max retries exceeded after {failure_count} attempts: {error}",
            )

    def _estimate_output_tokens(self, task_description: str) -> int:
        """Estimate expected output tokens based on task description."""
        return estimate_output_tokens(task_description)


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
