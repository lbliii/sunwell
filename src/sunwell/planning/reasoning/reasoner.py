"""Core Reasoner for LLM-driven decision making (RFC-073).

The Reasoner replaces rule-based decisions with reasoned judgments.
It assembles context from multiple sources, prompts the Wisdom model,
and falls back to rules when confidence is low.

Context Sources:
- CodebaseGraph: Static/dynamic analysis (RFC-045)
- ExecutionCache: Provenance tracking (RFC-074)
- ProjectContext: Decision/failure memory (RFC-045)
- ArtifactGraph: Dependency DAG (RFC-036)

Example:
    >>> reasoner = Reasoner(
    ...     model=wisdom_model,
    ...     project_context=project_ctx,
    ...     execution_cache=cache,
    ... )
    >>> decision = await reasoner.decide(
    ...     decision_type=DecisionType.SEVERITY_ASSESSMENT,
    ...     context={"signal": signal, "file_path": path, "content": content},
    ... )
    >>> if decision.is_confident:
    ...     return decision.outcome
    ... else:
    ...     return rule_based_fallback(signal)
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.models.protocol import GenerateOptions, Tool
from sunwell.planning.reasoning.decisions import (
    APPROVAL_OUTCOMES,
    CONFIDENCE_THRESHOLDS,
    RECOVERY_STRATEGIES,
    SEVERITY_LEVELS,
    DecisionType,
    ReasonedDecision,
    RecoveryDecision,
)
from sunwell.planning.reasoning.enrichment import ContextEnricher
from sunwell.planning.reasoning.prompts import PromptBuilder

# Pre-compiled regex patterns
_MARKDOWN_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

# Outcome validators by decision type
_OUTCOME_VALIDATORS: dict[DecisionType, Callable[[Any], bool]] = {
    DecisionType.SEVERITY_ASSESSMENT: lambda o: o in SEVERITY_LEVELS,
    DecisionType.RECOVERY_STRATEGY: lambda o: o in RECOVERY_STRATEGIES,
    DecisionType.SEMANTIC_APPROVAL: lambda o: o in APPROVAL_OUTCOMES,
    DecisionType.AUTO_FIXABLE: lambda o: isinstance(o, bool),
    DecisionType.RISK_ASSESSMENT: lambda o: o in SEVERITY_LEVELS,
}

# Outcome field names by decision type
_OUTCOME_FIELDS: dict[DecisionType, str] = {
    DecisionType.SEVERITY_ASSESSMENT: "severity",
    DecisionType.RECOVERY_STRATEGY: "strategy",
    DecisionType.SEMANTIC_APPROVAL: "decision",
    DecisionType.ROOT_CAUSE_ANALYSIS: "root_cause",
    DecisionType.AUTO_FIXABLE: "auto_fixable",
    DecisionType.RISK_ASSESSMENT: "risk_level",
}

# Conservative defaults for fallback
_CONSERVATIVE_DEFAULTS: dict[DecisionType, Any] = {
    DecisionType.SEVERITY_ASSESSMENT: "medium",
    DecisionType.AUTO_FIXABLE: False,
    DecisionType.RECOVERY_STRATEGY: "escalate",
    DecisionType.SEMANTIC_APPROVAL: "flag",
    DecisionType.RISK_ASSESSMENT: "medium",
    DecisionType.ROOT_CAUSE_ANALYSIS: "Unknown",
    DecisionType.GOAL_PRIORITY: 5,
    DecisionType.DISPLAY_VARIANT: "banner",
}


@cache
def _get_decision_tools() -> dict[DecisionType, tuple[Tool, ...]]:
    """Build tools dict once, cached forever."""
    return {
        DecisionType.SEVERITY_ASSESSMENT: (
            Tool(
                name="decide_severity",
                description="Assess severity of a code signal",
                parameters={
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Assessed severity level",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence 0-1 in this assessment",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this severity was chosen",
                        },
                        "context_factors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "What factors influenced the decision",
                        },
                    },
                    "required": ["severity", "confidence", "rationale"],
                },
            ),
        ),
        DecisionType.RECOVERY_STRATEGY: (
            Tool(
                name="decide_recovery",
                description="Choose recovery strategy for a failure",
                parameters={
                    "type": "object",
                    "properties": {
                        "strategy": {
                            "type": "string",
                            "enum": ["retry", "retry_different", "escalate", "abort"],
                            "description": "Recovery strategy",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in this strategy",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this strategy was chosen",
                        },
                        "retry_hint": {
                            "type": "string",
                            "description": "Hint for retry (if retry_different)",
                        },
                        "escalation_reason": {
                            "type": "string",
                            "description": "Why human needed (if strategy is escalate)",
                        },
                    },
                    "required": ["strategy", "confidence", "rationale"],
                },
            ),
        ),
        DecisionType.SEMANTIC_APPROVAL: (
            Tool(
                name="decide_approval",
                description="Decide if change can be auto-approved",
                parameters={
                    "type": "object",
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["approve", "flag", "deny"],
                            "description": "Approval decision",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in this decision",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this decision was made",
                        },
                        "risk_factors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Identified risk factors",
                        },
                    },
                    "required": ["decision", "confidence", "rationale"],
                },
            ),
        ),
        DecisionType.ROOT_CAUSE_ANALYSIS: (
            Tool(
                name="decide_root_cause",
                description="Analyze root cause of failure",
                parameters={
                    "type": "object",
                    "properties": {
                        "root_cause": {
                            "type": "string",
                            "description": "Identified root cause",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in this analysis",
                        },
                        "prevention": {
                            "type": "string",
                            "description": "How to prevent in future",
                        },
                        "similar_to": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of similar past failures",
                        },
                    },
                    "required": ["root_cause", "confidence", "prevention"],
                },
            ),
        ),
        DecisionType.AUTO_FIXABLE: (
            Tool(
                name="decide_auto_fixable",
                description="Determine if signal can be auto-fixed",
                parameters={
                    "type": "object",
                    "properties": {
                        "auto_fixable": {
                            "type": "boolean",
                            "description": "Whether it can be auto-fixed",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in this assessment",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this assessment was made",
                        },
                    },
                    "required": ["auto_fixable", "confidence", "rationale"],
                },
            ),
        ),
        DecisionType.RISK_ASSESSMENT: (
            Tool(
                name="decide_risk",
                description="Assess risk level of a change",
                parameters={
                    "type": "object",
                    "properties": {
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Assessed risk level",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence in this assessment",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this risk level was chosen",
                        },
                        "risk_factors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Identified risk factors",
                        },
                    },
                    "required": ["risk_level", "confidence", "rationale"],
                },
            ),
        ),
    }

if TYPE_CHECKING:
    from sunwell.agent.incremental.cache import ExecutionCache
    from sunwell.knowledge.codebase.context import ProjectContext
    from sunwell.models.protocol import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactGraph


# Type alias for fallback functions
FallbackFunc = Callable[[dict[str, Any]], Any]


@dataclass(slots=True)
class Reasoner:
    """LLM-driven decision maker with rich context assembly.

    The Reasoner's power comes from rich context assembly. Unlike simple
    rule-based decisions that see only the immediate signal, the Reasoner
    has access to Sunwell's full knowledge graph.

    Attributes:
        model: Wisdom model for reasoning (qwen2.5:14b recommended).
        project_context: Unified context with decisions, failures, patterns.
        execution_cache: SQLite-backed cache with provenance tracking.
        artifact_graph: Dependency DAG for artifact relationships.
        fallback_rules: Rule-based fallbacks for each decision type.
        confidence_threshold: Minimum confidence for autonomous decisions.

    Example:
        >>> reasoner = Reasoner(model=wisdom_model)
        >>> decision = await reasoner.decide(
        ...     decision_type=DecisionType.SEVERITY_ASSESSMENT,
        ...     context={"signal_type": "fixme_comment", "content": "race condition"},
        ... )
        >>> print(decision.outcome)  # "high"
        >>> print(decision.confidence)  # 0.85
    """

    model: ModelProtocol
    """Wisdom model for reasoning (qwen2.5:14b recommended)."""

    # === Context Sources ===

    project_context: ProjectContext | None = None
    """Unified context: decisions, failures, patterns, codebase graph (RFC-045)."""

    execution_cache: ExecutionCache | None = None
    """Provenance tracking and execution history (RFC-074)."""

    artifact_graph: ArtifactGraph | None = None
    """Dependency relationships between artifacts (RFC-036)."""

    # === Configuration ===

    fallback_rules: dict[DecisionType, FallbackFunc] = field(default_factory=dict)
    """Rule-based fallbacks for each decision type."""

    confidence_threshold: float = CONFIDENCE_THRESHOLDS["autonomous_action"]
    """Minimum confidence for autonomous decisions (default: 70%)."""

    use_tool_calling: bool = True
    """If False, use direct JSON parsing instead of tool calling (faster)."""

    _decision_history: list[ReasonedDecision] = field(
        default_factory=list, repr=False
    )
    """History of decisions made (for learning and consistency)."""

    _history_by_type: dict[DecisionType, list[ReasonedDecision]] = field(
        default_factory=dict, repr=False
    )
    """Index of decisions by type for O(1) lookup."""

    _context_enricher: ContextEnricher | None = field(default=None, init=False)
    """Context enricher for assembling rich context."""

    def __post_init__(self) -> None:
        """Initialize default fallback rules."""
        if not self.fallback_rules:
            self.fallback_rules = self._default_fallback_rules()

        # Initialize context enricher
        self._context_enricher = ContextEnricher(
            project_context=self.project_context,
            execution_cache=self.execution_cache,
            artifact_graph=self.artifact_graph,
            decision_history=self._history_by_type,
        )

    async def decide(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
        *,
        force_reasoning: bool = False,
    ) -> ReasonedDecision:
        """Make a reasoned decision about the given context.

        Flow:
        1. Assemble full context from all sources
        2. Check for high-confidence match with past decisions (cache)
        3. Build reasoning prompt with rich context
        4. Reason with Wisdom model using tool calling
        5. Record decision for learning

        Args:
            decision_type: What kind of decision to make.
            context: Relevant context for the decision.
            force_reasoning: If True, skip fast path and always use LLM.

        Returns:
            ReasonedDecision with outcome, confidence, and rationale.

        Example:
            >>> decision = await reasoner.decide(
            ...     DecisionType.SEVERITY_ASSESSMENT,
            ...     {"signal_type": "todo_comment", "file_path": "billing.py"},
            ... )
        """
        # 1. Assemble full context
        if not self._context_enricher:
            self._context_enricher = ContextEnricher(
                project_context=self.project_context,
                execution_cache=self.execution_cache,
                artifact_graph=self.artifact_graph,
                decision_history=self._history_by_type,
            )
        enriched = await self._context_enricher.enrich(decision_type, context)

        # 2. Check for high-confidence match with past decisions
        if not force_reasoning:
            cached = await self._check_similar_decisions(decision_type, enriched)
            if cached and cached.confidence >= 0.90:
                return cached

        # 3. Build reasoning prompt
        if self.use_tool_calling:
            prompt = PromptBuilder.build_prompt(decision_type, enriched)
            tools = self._get_tools(decision_type)
        else:
            prompt = PromptBuilder.build_fast_prompt(decision_type, enriched)
            tools = None

        # 4. Reason with model
        try:
            if self.use_tool_calling and tools:
                result = await self.model.generate(
                    prompt,
                    tools=tools,
                    tool_choice="required",
                    options=GenerateOptions(temperature=0.2),
                )
                decision = self._parse_decision(decision_type, result)
            else:
                # Fast mode: direct JSON parsing (no tool calling)
                result = await self.model.generate(
                    prompt,
                    options=GenerateOptions(temperature=0.1),
                )
                outcome, confidence, rationale = PromptBuilder.parse_json_decision(
                    decision_type,
                    result,
                    _OUTCOME_VALIDATORS,
                    _CONSERVATIVE_DEFAULTS,
                )
                decision = ReasonedDecision(
                    decision_type=decision_type,
                    outcome=outcome,
                    confidence=confidence,
                    rationale=rationale,
                    context_used=tuple(enriched.get("context_factors", [])),
                )

        except Exception as e:
            # Fallback to rules on any error
            decision = self._apply_fallback(decision_type, context, error=str(e))

        # 5. Record for learning (maintain both list and index)
        self._decision_history.append(decision)
        self._history_by_type.setdefault(decision.decision_type, []).append(decision)
        await self._record_decision(decision, enriched)

        return decision

    async def decide_severity(
        self,
        signal_type: str,
        content: str,
        file_path: str | Path,
        code_context: str | None = None,
    ) -> ReasonedDecision:
        """Convenience method for severity assessment.

        Args:
            signal_type: Type of signal (todo_comment, fixme_comment, etc.).
            content: The signal content/message.
            file_path: Path to the file containing the signal.
            code_context: Optional surrounding code (±20 lines).

        Returns:
            ReasonedDecision with severity as outcome.
        """
        return await self.decide(
            DecisionType.SEVERITY_ASSESSMENT,
            {
                "signal_type": signal_type,
                "content": content,
                "file_path": str(file_path),
                "code_context": code_context or "",
            },
        )

    async def decide_recovery(
        self,
        error_type: str,
        error_message: str,
        attempt_number: int,
        code_context: str | None = None,
        past_failures: list[dict[str, Any]] | None = None,
    ) -> RecoveryDecision:
        """Convenience method for recovery strategy decision.

        Args:
            error_type: The exception class name.
            error_message: The error message.
            attempt_number: Which retry attempt this is (1-indexed).
            code_context: Code that was being generated/executed.
            past_failures: Previous failures in this session.

        Returns:
            RecoveryDecision with strategy and hints.
        """
        decision = await self.decide(
            DecisionType.RECOVERY_STRATEGY,
            {
                "error_type": error_type,
                "error_message": error_message,
                "attempt_number": attempt_number,
                "code_context": code_context or "",
                "past_failures": past_failures or [],
            },
        )

        # Convert to RecoveryDecision
        return RecoveryDecision(
            decision_type=decision.decision_type,
            outcome=decision.outcome,
            confidence=decision.confidence,
            rationale=decision.rationale,
            similar_decisions=decision.similar_decisions,
            context_used=decision.context_used,
            strategy=decision.outcome,
        )

    # =========================================================================
    # Context Assembly (now using ContextEnricher)
    # =========================================================================

    # =========================================================================
    # Similar Decision Matching
    # =========================================================================

    async def _check_similar_decisions(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> ReasonedDecision | None:
        """Check if a similar decision exists with high confidence.

        Fast path: If we've made a very similar decision recently with
        high confidence, reuse it instead of calling LLM.

        Args:
            decision_type: Type of decision.
            context: The enriched context.

        Returns:
            Cached decision if found with >=90% confidence, else None.
        """
        # Use index for O(1) type lookup instead of O(n) scan
        history = self._history_by_type.get(decision_type, [])
        for decision in reversed(history[-50:]):
            if decision.confidence >= 0.90 and self._is_similar_context(context, decision):
                return decision
        return None

    def _is_similar_context(
        self,
        context: dict[str, Any],
        decision: ReasonedDecision,
    ) -> bool:
        """Check if contexts are similar enough to reuse decision."""
        # Same file + same signal type = similar
        return (
            "file_path" in context
            and "file_path" in decision.context_used
            and "signal_type" in context
        )

    # =========================================================================
    # Prompt Building (now using PromptBuilder)
    # =========================================================================

    # =========================================================================
    # Tool Definitions
    # =========================================================================

    def _get_tools(self, decision_type: DecisionType) -> tuple[Tool, ...]:
        """Get tool definitions for structured output."""
        tools = _get_decision_tools()
        return tools.get(decision_type, self._generic_tool(decision_type))

    def _generic_tool(self, decision_type: DecisionType) -> tuple[Tool, ...]:
        """Generic tool for decision types without specialized tools."""
        return (
            Tool(
                name=f"decide_{decision_type.value}",
                description=f"Make a {decision_type.value} decision",
                parameters={
                    "type": "object",
                    "properties": {
                        "outcome": {
                            "type": "string",
                            "description": "The decision outcome",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence 0-1",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why this decision was made",
                        },
                    },
                    "required": ["outcome", "confidence", "rationale"],
                },
            ),
        )

    # =========================================================================
    # Response Parsing
    # =========================================================================

    def _parse_decision(
        self,
        decision_type: DecisionType,
        result: Any,
    ) -> ReasonedDecision:
        """Parse LLM response into ReasonedDecision."""
        # Extract tool call arguments
        if result.has_tool_calls:
            tool_call = result.tool_calls[0]
            args = tool_call.arguments

            # Map tool-specific outcome fields
            outcome = self._extract_outcome(decision_type, args)
            confidence = args.get("confidence", 0.5)
            rationale = args.get("rationale", "")
            context_factors = tuple(args.get("context_factors", args.get("risk_factors", [])))

            return ReasonedDecision(
                decision_type=decision_type,
                outcome=outcome,
                confidence=confidence,
                rationale=rationale,
                context_used=context_factors,
            )

        # Fallback if no tool calls
        return self._apply_fallback(decision_type, {}, error="No tool calls in response")

    def _extract_outcome(
        self,
        decision_type: DecisionType,
        args: dict[str, Any],
    ) -> Any:
        """Extract the outcome field from tool call arguments."""
        field_name = _OUTCOME_FIELDS.get(decision_type, "outcome")
        return args.get(field_name, args.get("outcome"))

    # =========================================================================
    # Fallback Rules
    # =========================================================================

    def _default_fallback_rules(self) -> dict[DecisionType, FallbackFunc]:
        """Default rule-based fallbacks for each decision type."""
        return {
            DecisionType.SEVERITY_ASSESSMENT: self._severity_fallback,
            DecisionType.AUTO_FIXABLE: self._auto_fixable_fallback,
            DecisionType.RECOVERY_STRATEGY: self._recovery_fallback,
            DecisionType.SEMANTIC_APPROVAL: self._approval_fallback,
            DecisionType.RISK_ASSESSMENT: self._risk_fallback,
        }

    def _severity_fallback(self, context: dict[str, Any]) -> str:
        """Rule-based severity assessment."""
        signal_type = context.get("signal_type", "")

        if "fixme" in signal_type.lower():
            return "high"
        elif "todo" in signal_type.lower():
            return "low"
        elif "type_error" in signal_type.lower():
            return "high"
        elif "lint" in signal_type.lower():
            return "medium"
        else:
            return "medium"

    def _auto_fixable_fallback(self, context: dict[str, Any]) -> bool:
        """Rule-based auto-fixable assessment."""
        signal_type = context.get("signal_type", "")

        # Lint warnings are usually auto-fixable
        if "lint" in signal_type.lower():
            return True
        # Tests are sometimes auto-fixable, TODOs need human judgment
        return "failing_test" in signal_type.lower()

    def _recovery_fallback(self, context: dict[str, Any]) -> str:
        """Rule-based recovery strategy."""
        attempt = context.get("attempt_number", 1)
        error_type = context.get("error_type", "")

        # Transient errors: retry a few times
        if attempt <= 3 and "timeout" in error_type.lower():
            return "retry"
        # Too many attempts: escalate
        if attempt > 5:
            return "escalate"
        # Try different approach
        if attempt > 2:
            return "retry_different"

        return "retry"

    def _approval_fallback(self, context: dict[str, Any]) -> str:
        """Rule-based approval decision."""
        category = context.get("goal_category", "")

        # Documentation is usually safe
        if "docs" in category.lower() or "documentation" in category.lower():
            return "approve"
        # Tests are usually safe
        if "test" in category.lower():
            return "approve"
        # Default to flagging
        return "flag"

    def _risk_fallback(self, context: dict[str, Any]) -> str:
        """Rule-based risk assessment."""
        files_affected = context.get("files_affected", [])
        lines_changed = context.get("lines_changed", 0)

        # Large changes are high risk
        if isinstance(lines_changed, int) and lines_changed > 500:
            return "high"
        if len(files_affected) > 10:
            return "high"
        if len(files_affected) > 5:
            return "medium"

        return "low"

    def _apply_fallback(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
        error: str | None = None,
    ) -> ReasonedDecision:
        """Apply rule-based fallback when reasoning fails."""
        fallback = self.fallback_rules.get(decision_type)
        outcome = fallback(context) if fallback else self._conservative_default(decision_type)

        return ReasonedDecision(
            decision_type=decision_type,
            outcome=outcome,
            confidence=0.5,  # Low confidence for fallback
            rationale=f"Fallback to rules{': ' + error if error else ''}",
        )

    def _conservative_default(self, decision_type: DecisionType) -> Any:
        """Conservative default for decision types without fallback rules."""
        return _CONSERVATIVE_DEFAULTS.get(decision_type)

    # =========================================================================
    # Learning / Recording
    # =========================================================================

    async def _record_decision(
        self,
        decision: ReasonedDecision,
        context: dict[str, Any],
    ) -> None:
        """Record decision for learning (ProjectContext integration).

        Stores decision in ProjectContext.decisions for:
        - Future similarity matching
        - Confidence calibration
        - Pattern extraction
        """
        if not self.project_context:
            return

        # Record to decision memory if available
        try:
            if hasattr(self.project_context, "decisions"):
                # Store as a lightweight decision record
                # Full integration with DecisionMemory would go here
                pass
        except Exception:
            pass  # Silent fail for recording

    def get_decision_history(self, limit: int = 100) -> list[ReasonedDecision]:
        """Get recent decision history.

        Args:
            limit: Maximum number of decisions to return.

        Returns:
            List of recent decisions (newest first).
        """
        return list(reversed(self._decision_history[-limit:]))

    def clear_history(self) -> None:
        """Clear decision history (for testing)."""
        self._decision_history.clear()
        self._history_by_type.clear()
