"""Main runtime engine - orchestrates lens execution.

Extended with tool calling support per RFC-012.
Extended with memory tools per RFC-014.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, TYPE_CHECKING, Union

from sunwell.core.lens import Lens
from sunwell.core.types import Tier, Confidence
from sunwell.core.errors import SunwellError, ErrorCode
from sunwell.core.validator import ValidationResult
from sunwell.core.persona import PersonaResult
from sunwell.models.protocol import (
    ModelProtocol,
    GenerateOptions,
    GenerateResult,
    TokenUsage,
    Message,
    Tool,
    ToolCall,
)
from sunwell.embedding.protocol import EmbeddingProtocol
from sunwell.runtime.classifier import IntentClassifier
from sunwell.runtime.retriever import ExpertiseRetriever
from sunwell.runtime.injector import ContextInjector

if TYPE_CHECKING:
    from sunwell.workspace.indexer import CodebaseIndexer
    from sunwell.tools.executor import ToolExecutor
    from sunwell.tools.types import ToolResult
    from sunwell.fount.client import FountClient
    from sunwell.runtime.model_router import ModelRouter
    from sunwell.simulacrum.core.store import SimulacrumStore
    from sunwell.routing.cognitive_router import CognitiveRouter
    from sunwell.core.spell import Spell, Grimoire, SpellResult


# =============================================================================
# Streaming Event Types (RFC-012)
# =============================================================================

@dataclass(frozen=True, slots=True)
class TextEvent:
    """Streamed text chunk."""
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    """Tool is being called (stream pauses)."""
    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    """Tool result (stream resumes)."""
    tool_call: ToolCall
    result: "ToolResult"


@dataclass(frozen=True, slots=True)
class DoneEvent:
    """Stream complete."""
    total_tool_calls: int
    truncated: bool = False


# Union type for stream events
StreamEvent = Union[TextEvent, ToolCallEvent, ToolResultEvent, DoneEvent]


# =============================================================================
# Result Types
# =============================================================================

@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result from lens execution."""

    content: str
    tier: Tier
    confidence: Confidence
    validation_results: tuple[ValidationResult, ...]
    persona_results: tuple[PersonaResult, ...] = ()
    refinement_count: int = 0
    token_usage: TokenUsage | None = None
    retrieved_components: tuple[str, ...] = ()
    retrieved_code: tuple[str, ...] = ()  # File references for retrieved code


@dataclass(frozen=True, slots=True)
class ToolAwareResult:
    """Result from tool-aware execution (RFC-012)."""
    
    content: str
    tool_history: tuple[tuple[ToolCall, "ToolResult"], ...] = ()
    total_tool_calls: int = 0
    truncated: bool = False  # True if max_tool_calls reached
    token_usage: TokenUsage | None = None


@dataclass
class RuntimeEngine:
    """The main Sunwell runtime engine.

    Orchestrates:
    1. Intent classification → determine tier
    2. Expertise retrieval → select relevant lens components
    3. Codebase retrieval → find relevant project code (if indexed)
    4. Context injection → build prompt with expertise + code
    5. Model execution → generate response
    6. Validation → run quality gates
    7. Refinement → iterate if needed
    
    RFC-012 Extension:
    8. Tool execution → execute tool calls from model
    9. Tool loop → iterate until model produces final response
    
    RFC-014 Extension:
    10. Memory tools → LLM can search/add to multi-topology memory
    """

    model: ModelProtocol
    lens: Lens

    # Optional dependencies
    embedder: EmbeddingProtocol | None = None
    codebase_indexer: "CodebaseIndexer | None" = None
    tool_executor: "ToolExecutor | None" = None  # RFC-012
    fount_client: "FountClient | None" = None  # Phase 7
    model_router: "ModelRouter | None" = None  # RFC-015
    simulacrum_store: "SimulacrumStore | None" = None  # RFC-014
    cognitive_router: "CognitiveRouter | None" = None  # RFC-020
    grimoire: "Grimoire | None" = None  # RFC-021

    # Sub-components (lazily initialized)
    _classifier: IntentClassifier | None = field(default=None, init=False)
    _retriever: ExpertiseRetriever | None = field(default=None, init=False)
    _injector: ContextInjector | None = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    _last_routing_decision: dict | None = field(default=None, init=False)
    _last_spell: "Spell | None" = field(default=None, init=False)  # RFC-021

    async def execute(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
        force_tier: Tier | None = None,
    ) -> ExecutionResult:
        """Execute a prompt through the lens.

        1. Classify intent to determine execution tier
        2. Retrieve relevant expertise components
        3. Retrieve relevant codebase context (if workspace indexed)
        4. Inject context and execute model
        5. Run validation and persona testing
        6. Refine if needed (up to retry_limit)
        """
        if not self._initialized:
            await self._initialize_components()

        # Step 1: Classify intent
        tier = force_tier or self._classify_intent(prompt)

        # RFC-015: Adaptive Model Selection
        if self.model_router:
            # Optionally switch model based on tier
            recommended_model = await self.model_router.route(prompt, tier=tier)
            if recommended_model != self.model.model_id:
                # We could potentially switch models here, but for now
                # let's just log it or allow the router to handle it
                pass

        # RFC-020/021: Cognitive routing with spell support
        self._last_routing_decision = None
        self._last_spell = None
        spell_context = ""
        
        if self.cognitive_router and tier != Tier.FAST_PATH:
            # Use route_with_spell for full context
            routing, spell = await self.cognitive_router.route_with_spell(prompt)
            self._last_routing_decision = routing.to_dict()
            self._last_spell = spell
            
            # RFC-021: Build spell context if spell was matched
            if spell:
                template_vars = self._get_template_vars(prompt)
                spell_context = spell.to_system_context(template_vars)
        
        # Step 2: Retrieve relevant lens components (skip for FAST_PATH)
        retrieved_components: tuple[str, ...] = ()
        if tier != Tier.FAST_PATH and self._retriever:
            if self._last_routing_decision and self.cognitive_router:
                # Use routed retrieval with focus boosting
                from sunwell.routing.cognitive_router import RoutingDecision
                routing = RoutingDecision.from_dict(self._last_routing_decision)
                retrieval = await self._retriever.retrieve_with_routing(prompt, routing)
            else:
                # Standard retrieval
                retrieval = await self._retriever.retrieve(prompt)
            retrieved_components = tuple(h.name for h in retrieval.heuristics)
            
            # RFC-021: Load reagents from spell (force specific heuristics)
            if self._last_spell and self._last_spell.reagents:
                reagent_names = self._get_reagent_components(self._last_spell)
                retrieved_components = tuple(
                    set(retrieved_components) | set(reagent_names)
                )

        # Step 3: Retrieve relevant codebase context
        code_context = ""
        retrieved_code: tuple[str, ...] = ()
        if self.codebase_indexer:
            code_retrieval = await self.codebase_indexer.retrieve(prompt, top_k=5)
            if code_retrieval.chunks:
                code_context = code_retrieval.to_prompt_context()
                retrieved_code = tuple(c.reference for c in code_retrieval.chunks)

        # Step 4: Build context and execute
        lens_context = self._injector.build_context(  # type: ignore
            self.lens,
            retrieved_components if retrieved_components else None,
        )

        # Combine lens expertise + spell context + codebase context
        full_prompt_parts = [lens_context]
        
        # RFC-021: Add spell context (instructions, template, quality gates)
        if spell_context:
            full_prompt_parts.append(spell_context)
        
        if code_context:
            full_prompt_parts.append(code_context)
        full_prompt_parts.append(f"---\n\n## Task\n\n{prompt}")
        
        full_prompt = "\n\n".join(full_prompt_parts)

        result = await self._execute_with_retry(full_prompt, options)

        # Step 5+6: Run validators AND personas in PARALLEL
        # This is the big win - 8 API calls (4 validators + 4 personas)
        # now complete in ~1x latency instead of 8x
        validation_results: tuple[ValidationResult, ...] = ()
        persona_results: tuple[PersonaResult, ...] = ()
        
        if tier == Tier.DEEP_LENS:
            # Maximum parallelism: validators + personas simultaneously
            val_task = self._run_validators(result.content)
            persona_task = self._run_personas(result.content)
            validation_results, persona_results = await asyncio.gather(
                val_task, persona_task
            )
        elif tier != Tier.FAST_PATH:
            # Standard tier: just validators (still parallel within)
            validation_results = await self._run_validators(result.content)

        # Step 7: Check quality and potentially refine
        refinement_count = 0
        while not self._passes_quality_policy(validation_results, persona_results):
            if refinement_count >= self.lens.quality_policy.retry_limit:
                break

            # Refine based on feedback, then re-validate in parallel
            result = await self._refine(
                result.content, validation_results, persona_results, options
            )
            
            # Re-run validation (parallel within each group)
            if tier == Tier.DEEP_LENS:
                validation_results, persona_results = await asyncio.gather(
                    self._run_validators(result.content),
                    self._run_personas(result.content),
                )
            else:
                validation_results = await self._run_validators(result.content)
            
            refinement_count += 1

        # Compute confidence
        confidence = self._compute_confidence(validation_results, persona_results)

        return ExecutionResult(
            content=result.content,
            tier=tier,
            confidence=confidence,
            validation_results=validation_results,
            persona_results=persona_results,
            refinement_count=refinement_count,
            token_usage=result.usage,
            retrieved_components=retrieved_components,
            retrieved_code=retrieved_code,
        )

    async def execute_stream(
        self,
        prompt: str,
        *,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[str]:
        """Stream execution for real-time output.

        Note: Streaming skips validation and persona testing.
        Use execute() for full quality gates.
        """
        if not self._initialized:
            await self._initialize_components()

        # Classify and retrieve lens components
        tier = self._classify_intent(prompt)

        # RFC-020: Cognitive routing for streaming
        self._last_routing_decision = None
        if self.cognitive_router and tier != Tier.FAST_PATH:
            routing = await self.cognitive_router.route(prompt)
            self._last_routing_decision = routing.to_dict()

        retrieved_components: tuple[str, ...] = ()
        if tier != Tier.FAST_PATH and self._retriever:
            if self._last_routing_decision and self.cognitive_router:
                from sunwell.routing.cognitive_router import RoutingDecision
                routing = RoutingDecision.from_dict(self._last_routing_decision)
                retrieval = await self._retriever.retrieve_with_routing(prompt, routing)
            else:
                retrieval = await self._retriever.retrieve(prompt)
            retrieved_components = tuple(h.name for h in retrieval.heuristics)

        # Retrieve codebase context
        code_context = ""
        if self.codebase_indexer:
            code_retrieval = await self.codebase_indexer.retrieve(prompt, top_k=5)
            if code_retrieval.chunks:
                code_context = code_retrieval.to_prompt_context()

        # Build context
        lens_context = self._injector.build_context(  # type: ignore
            self.lens,
            retrieved_components if retrieved_components else None,
        )

        # Combine lens expertise + codebase context
        full_prompt_parts = [lens_context]
        if code_context:
            full_prompt_parts.append(code_context)
        full_prompt_parts.append(f"---\n\n## Task\n\n{prompt}")
        
        full_prompt = "\n\n".join(full_prompt_parts)

        # Stream response
        async for chunk in self.model.generate_stream(full_prompt, options=options):
            yield chunk

    # =========================================================================
    # Tool-Aware Execution (RFC-012)
    # =========================================================================

    async def execute_with_tools(
        self,
        prompt: str,
        *,
        max_tool_calls: int = 10,
        allowed_tools: set[str] | None = None,  # None = all tools
        include_memory_tools: bool = True,  # RFC-014
        options: GenerateOptions | None = None,
    ) -> ToolAwareResult:
        """Execute with automatic tool calling loop (RFC-012/014).
        
        Args:
            prompt: User request
            max_tool_calls: Safety limit on iterations
            allowed_tools: Restrict to specific tools (None = all)
            include_memory_tools: Include RFC-014 memory tools (default True)
            options: Generation options
            
        Returns:
            ToolAwareResult with content, tool history, and stats
        """
        if not self.tool_executor:
            raise SunwellError(
                code=ErrorCode.RUNTIME_STATE_INVALID,
                context={"detail": "ToolExecutor not configured. Set tool_executor on RuntimeEngine."},
            )
        
        if not self._initialized:
            await self._initialize_components()
        
        # Collect available tools (including memory tools if enabled)
        tools = self._collect_tools(
            allowed_tools=allowed_tools,
            include_memory_tools=include_memory_tools,
        )
        
        # Add skill-derived tools from lens
        if hasattr(self.lens, 'skills') and self.lens.skills:
            for skill in self.lens.skills:
                if hasattr(skill, 'parameters_schema') and skill.parameters_schema:
                    tool = skill.to_tool()
                    if allowed_tools is None or tool.name in allowed_tools:
                        tools.append(tool)
        
        # Build initial message history
        messages: list[Message] = [
            Message(role="user", content=prompt)
        ]
        
        tool_history: list[tuple[ToolCall, "ToolResult"]] = []
        total_calls = 0
        
        for iteration in range(max_tool_calls):
            # Generate with tools available
            result = await self.model.generate(
                tuple(messages),
                tools=tuple(tools),
                tool_choice="auto",
                options=options,
            )
            
            # If no tool calls, we're done
            if not result.has_tool_calls:
                return ToolAwareResult(
                    content=result.text,
                    tool_history=tuple(tool_history),
                    total_tool_calls=total_calls,
                    token_usage=result.usage,
                )
            
            # Execute tool calls
            for tool_call in result.tool_calls:
                total_calls += 1
                tool_result = await self.tool_executor.execute(tool_call)
                tool_history.append((tool_call, tool_result))
            
            # Add assistant message with tool calls
            messages.append(Message(
                role="assistant",
                content=result.content,
                tool_calls=result.tool_calls,
            ))
            
            # Add tool result messages
            for tool_call, tool_result in tool_history[-len(result.tool_calls):]:
                messages.append(Message(
                    role="tool",
                    content=tool_result.output,
                    tool_call_id=tool_call.id,
                ))
        
        # Max iterations reached - generate final response without tools
        final_result = await self.model.generate(
            tuple(messages),
            tools=None,  # No tools for final response
            options=options,
        )
        
        return ToolAwareResult(
            content=final_result.text or "Maximum tool calls reached without completion.",
            tool_history=tuple(tool_history),
            total_tool_calls=total_calls,
            truncated=True,
            token_usage=final_result.usage,
        )

    async def execute_stream_with_tools(
        self,
        prompt: str,
        *,
        max_tool_calls: int = 10,
        allowed_tools: set[str] | None = None,
        options: GenerateOptions | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream execution with tool support (RFC-012).
        
        Yields StreamEvent objects:
        - TextEvent: Streamed text chunk
        - ToolCallEvent: Tool is being called (pause stream)
        - ToolResultEvent: Tool result (resume stream)
        - DoneEvent: Stream complete
        """
        if not self.tool_executor:
            raise SunwellError(
                code=ErrorCode.RUNTIME_STATE_INVALID,
                context={"detail": "ToolExecutor not configured"},
            )
        
        from sunwell.tools.builtins import CORE_TOOLS
        
        # Collect tools
        tools: list[Tool] = []
        for name, tool in CORE_TOOLS.items():
            if allowed_tools is None or name in allowed_tools:
                tools.append(tool)
        
        messages: list[Message] = [Message(role="user", content=prompt)]
        tool_count = 0
        
        while tool_count < max_tool_calls:
            # Generate (non-streaming for tool handling)
            result = await self.model.generate(
                tuple(messages),
                tools=tuple(tools),
                options=options,
            )
            
            # Yield text content
            if result.content:
                yield TextEvent(text=result.content)
            
            # If no tool calls, we're done
            if not result.has_tool_calls:
                yield DoneEvent(total_tool_calls=tool_count)
                return
            
            # Execute tool calls (stream pauses here)
            for tool_call in result.tool_calls:
                tool_count += 1
                yield ToolCallEvent(tool_call=tool_call)
                
                tool_result = await self.tool_executor.execute(tool_call)
                yield ToolResultEvent(tool_call=tool_call, result=tool_result)
                
                # Update message history
                messages.append(Message(
                    role="assistant",
                    content=result.content,
                    tool_calls=(tool_call,),
                ))
                messages.append(Message(
                    role="tool",
                    content=tool_result.output,
                    tool_call_id=tool_call.id,
                ))
        
        yield DoneEvent(total_tool_calls=tool_count, truncated=True)

    def _collect_tools(
        self,
        allowed_tools: set[str] | None = None,
        include_memory_tools: bool = True,
        include_expertise_tools: bool = True,
    ) -> list[Tool]:
        """Collect available tools for execution.
        
        Args:
            allowed_tools: Restrict to specific tools (None = all)
            include_memory_tools: Include RFC-014 memory tools (default True)
            include_expertise_tools: Include RFC-027 expertise tools (default True)
            
        Returns:
            List of Tool definitions for the model
        """
        from sunwell.tools.builtins import CORE_TOOLS
        
        tools: list[Tool] = []
        
        # Core file/shell tools
        for name, tool in CORE_TOOLS.items():
            if allowed_tools is None or name in allowed_tools:
                tools.append(tool)
        
        # RFC-014: Memory tools (always available when simulacrum_store is set)
        if include_memory_tools and self.simulacrum_store:
            from sunwell.simulacrum.memory_tools import MEMORY_TOOLS
            
            for name, tool in MEMORY_TOOLS.items():
                if allowed_tools is None or name in allowed_tools:
                    tools.append(tool)
        
        # RFC-027: Expertise tools (always available when tool_executor has expertise_handler)
        if include_expertise_tools and self.tool_executor and self.tool_executor.expertise_handler:
            from sunwell.tools.builtins import EXPERTISE_TOOLS
            
            for name, tool in EXPERTISE_TOOLS.items():
                if allowed_tools is None or name in allowed_tools:
                    tools.append(tool)
        
        return tools

    async def _initialize_components(self) -> None:
        """Initialize sub-components."""
        self._classifier = IntentClassifier(lens=self.lens)
        self._injector = ContextInjector()

        # Initialize retriever if embedder provided
        if self.embedder:
            self._retriever = ExpertiseRetriever(
                lens=self.lens,
                embedder=self.embedder,
            )
            await self._retriever.initialize()
        
        # RFC-014: Wire memory handler to tool executor
        if self.simulacrum_store and self.tool_executor:
            if self.simulacrum_store.memory_handler:
                self.tool_executor.memory_handler = self.simulacrum_store.memory_handler
        
        # RFC-027: Wire expertise handler to tool executor if retriever available
        if self._retriever and self.tool_executor and not self.tool_executor.expertise_handler:
            from sunwell.tools.expertise import ExpertiseToolHandler
            self.tool_executor.expertise_handler = ExpertiseToolHandler(
                retriever=self._retriever,
                lens=self.lens,
            )

        self._initialized = True

    def _classify_intent(self, prompt: str) -> Tier:
        """Classify prompt intent to determine tier."""
        if self._classifier:
            result = self._classifier.classify(prompt)
            return result.tier
        return Tier.STANDARD

    async def _execute_with_retry(
        self,
        prompt: str,
        options: GenerateOptions | None,
        max_retries: int = 3,
    ) -> GenerateResult:
        """Execute model call with exponential backoff retry."""
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await self.model.generate(prompt, options=options)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        raise last_error  # type: ignore

    async def _run_validators(self, content: str) -> tuple[ValidationResult, ...]:
        """Run heuristic validators on content in PARALLEL.
        
        Uses asyncio.gather for concurrent API calls - in Python 3.14 with
        free-threading, this achieves true parallelism. 4 validators that
        would take 4x API latency now complete in ~1x.
        """
        if not self.lens.heuristic_validators:
            return ()
        
        async def validate_one(validator) -> ValidationResult:
            """Run a single validator."""
            validation_prompt = validator.to_prompt(content)
            response = await self.model.generate(validation_prompt)
            
            # Parse response (format: PASS|0.95|explanation)
            try:
                parts = response.content.strip().split("|", 2)
                passed = parts[0].upper() == "PASS"
                confidence = float(parts[1]) if len(parts) > 1 else 0.5
                message = parts[2] if len(parts) > 2 else None
            except (ValueError, IndexError):
                passed = False
                confidence = 0.5
                message = response.content
            
            return ValidationResult(
                validator_name=validator.name,
                passed=passed,
                severity=validator.severity,
                message=message,
                confidence=confidence,
            )
        
        # Run ALL validators in parallel - major speedup!
        results = await asyncio.gather(*[
            validate_one(v) for v in self.lens.heuristic_validators
        ])
        
        return tuple(results)

    async def _run_personas(self, content: str) -> tuple[PersonaResult, ...]:
        """Run persona evaluations on content in PARALLEL.
        
        Uses asyncio.gather for concurrent API calls. 4 personas that
        would take 4x API latency now complete in ~1x.
        """
        if not self.lens.personas:
            return ()
        
        async def evaluate_one(persona) -> PersonaResult:
            """Run a single persona evaluation."""
            eval_prompt = persona.to_evaluation_prompt(content)
            response = await self.model.generate(eval_prompt)
            
            # Parse response - look for approval indicators
            response_lower = response.content.lower()
            approved = not any(
                word in response_lower
                for word in ["fail", "problem", "issue", "concern", "confused"]
            )
            
            return PersonaResult(
                persona_name=persona.name,
                approved=approved,
                feedback=response.content,
            )
        
        # Run ALL personas in parallel - major speedup!
        results = await asyncio.gather(*[
            evaluate_one(p) for p in self.lens.personas
        ])
        
        return tuple(results)

        return tuple(results)

    async def _refine(
        self,
        content: str,
        validations: tuple[ValidationResult, ...],
        personas: tuple[PersonaResult, ...],
        options: GenerateOptions | None,
    ) -> GenerateResult:
        """Refine content based on validation and persona feedback."""
        feedback_parts = []

        # Collect validation failures
        for v in validations:
            if not v.passed and v.message:
                feedback_parts.append(f"- {v.validator_name}: {v.message}")

        # Collect persona concerns
        for p in personas:
            if not p.approved:
                feedback_parts.append(f"- {p.persona_name}: {p.feedback[:200]}...")

        feedback = "\n".join(feedback_parts)

        refinement_prompt = f"""The following content needs improvement based on feedback:

## Original Content
{content}

## Feedback to Address
{feedback}

## Task
Revise the content to address all feedback while maintaining quality. Return only the improved content."""

        return await self.model.generate(refinement_prompt, options=options)

    def _passes_quality_policy(
        self,
        validations: tuple[ValidationResult, ...],
        personas: tuple[PersonaResult, ...],
    ) -> bool:
        """Check if results pass the lens quality policy."""
        policy = self.lens.quality_policy

        # If no validations, consider it passing
        if not validations and not personas:
            return True

        # Check required validators
        for req in policy.required_validators:
            matching = [v for v in validations if v.validator_name == req]
            if not matching or not matching[0].passed:
                return False

        # Check persona agreement
        if personas:
            approved = sum(1 for p in personas if p.approved)
            if approved / len(personas) < policy.persona_agreement:
                return False

        # Check overall validation pass rate
        if validations:
            passed = sum(1 for v in validations if v.passed)
            if passed / len(validations) < policy.min_confidence:
                return False

        return True

    def _compute_confidence(
        self,
        validations: tuple[ValidationResult, ...],
        personas: tuple[PersonaResult, ...],
    ) -> Confidence:
        """Compute overall confidence score."""
        if not validations and not personas:
            return Confidence(score=0.7, explanation="No validation performed")

        scores = []

        # Validator confidence (weighted higher)
        if validations:
            val_score = sum(1 for v in validations if v.passed) / len(validations)
            scores.append(("validators", val_score, 0.6))

        # Persona confidence
        if personas:
            persona_score = sum(1 for p in personas if p.approved) / len(personas)
            scores.append(("personas", persona_score, 0.4))

        # Compute weighted average
        if scores:
            total_weight = sum(w for _, _, w in scores)
            final_score = sum(s * w for _, s, w in scores) / total_weight
        else:
            final_score = 0.5

        explanation_parts = []
        for name, score, _ in scores:
            explanation_parts.append(f"{name}: {score:.0%}")

        return Confidence(
            score=final_score,
            explanation=", ".join(explanation_parts),
        )

    # =========================================================================
    # RFC-021: Spell Support Methods
    # =========================================================================

    def _get_template_vars(self, prompt: str) -> dict[str, str]:
        """Get template variables for spell context.

        Extracts file information from the prompt and provides built-in
        variables like date, time, user, lens name, etc.
        """
        import os
        import re
        from datetime import datetime

        now = datetime.now()
        vars_: dict[str, str] = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "lens": self.lens.metadata.name,
        }

        # Try to extract filename from prompt
        # Patterns: "review auth.py", "::security src/auth.py", etc.
        file_patterns = [
            r'(\S+\.\w{1,4})\s*$',  # file.ext at end
            r'(?:review|check|audit|analyze)\s+(\S+\.\w{1,4})',
            r'::\w+\s+(\S+\.\w{1,4})',  # ::command file.ext
        ]

        for pattern in file_patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                filepath = match.group(1)
                vars_["filepath"] = filepath
                vars_["filename"] = os.path.basename(filepath)

                # Detect language from extension
                ext_to_lang = {
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".go": "go",
                    ".rs": "rust",
                    ".java": "java",
                    ".rb": "ruby",
                    ".c": "c",
                    ".cpp": "cpp",
                    ".h": "c",
                    ".hpp": "cpp",
                    ".md": "markdown",
                    ".yaml": "yaml",
                    ".yml": "yaml",
                    ".json": "json",
                }
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ext_to_lang:
                    vars_["language"] = ext_to_lang[ext]
                break

        return vars_

    def _get_reagent_components(self, spell: "Spell") -> list[str]:
        """Get component names from spell reagents.

        Reagents specify which heuristics, personas, or validators
        should be force-loaded for the spell.
        """
        from sunwell.core.spell import ReagentType, ReagentMode

        component_names = []

        for reagent in spell.reagents:
            if reagent.type == ReagentType.HEURISTIC:
                # Add heuristic name to components to retrieve
                component_names.append(reagent.name)
            elif reagent.type == ReagentType.PERSONA:
                # Personas are handled separately (not in retrieval)
                pass
            elif reagent.type == ReagentType.VALIDATOR:
                # Validators are handled separately
                pass
            elif reagent.type == ReagentType.LENS:
                # Cross-lens references - future enhancement
                pass

        return component_names
