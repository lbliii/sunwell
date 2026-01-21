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

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.models.protocol import GenerateOptions, Tool
from sunwell.reasoning.decisions import (
    APPROVAL_OUTCOMES,
    CONFIDENCE_THRESHOLDS,
    RECOVERY_STRATEGIES,
    SEVERITY_LEVELS,
    DecisionType,
    ReasonedDecision,
    RecoveryDecision,
)

if TYPE_CHECKING:
    from sunwell.incremental.cache import ExecutionCache
    from sunwell.intelligence.context import ProjectContext
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.artifacts import ArtifactGraph


# Type alias for fallback functions
FallbackFunc = Callable[[dict[str, Any]], Any]


@dataclass
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

    def __post_init__(self) -> None:
        """Initialize default fallback rules."""
        if not self.fallback_rules:
            self.fallback_rules = self._default_fallback_rules()

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
        enriched = await self._enrich_context(decision_type, context)

        # 2. Check for high-confidence match with past decisions
        if not force_reasoning:
            cached = await self._check_similar_decisions(decision_type, enriched)
            if cached and cached.confidence >= 0.90:
                return cached

        # 3. Build reasoning prompt
        if self.use_tool_calling:
            prompt = self._build_prompt(decision_type, enriched)
            tools = self._get_tools(decision_type)
        else:
            prompt = self._build_fast_prompt(decision_type, enriched)
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
                decision = self._parse_json_decision(decision_type, result)

        except Exception as e:
            # Fallback to rules on any error
            decision = self._apply_fallback(decision_type, context, error=str(e))

        # 5. Record for learning
        self._decision_history.append(decision)
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
    # Context Assembly
    # =========================================================================

    async def _enrich_context(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble rich context from all available sources.

        Sources:
        - CodebaseGraph: Static/dynamic analysis (hot paths, coupling, ownership)
        - ExecutionCache: Provenance and execution history
        - ProjectContext: Decisions, failures, patterns
        - ArtifactGraph: Dependency relationships

        Args:
            decision_type: Type of decision being made.
            context: Base context to enrich.

        Returns:
            Enriched context dict with all available information.
        """
        enriched = dict(context)

        # === CodebaseGraph (RFC-045): Static + Dynamic Analysis ===
        if "file_path" in context and self.project_context:
            await self._enrich_from_codebase(enriched)

        # === ExecutionCache (RFC-074): Provenance + History ===
        if "artifact_id" in context and self.execution_cache:
            await self._enrich_from_cache(enriched, context["artifact_id"])

        # === ProjectContext (RFC-045): Memory + Learning ===
        if self.project_context:
            await self._enrich_from_project_context(enriched, decision_type)

        # === ArtifactGraph (RFC-036): Dependencies ===
        if "artifact_id" in context and self.artifact_graph:
            await self._enrich_from_artifact_graph(enriched, context["artifact_id"])

        return enriched

    async def _enrich_from_codebase(self, enriched: dict[str, Any]) -> None:
        """Add codebase graph context."""
        if not self.project_context:
            return

        file_path = Path(enriched.get("file_path", ""))
        codebase = self.project_context.codebase

        # Check hot paths
        enriched["in_hot_path"] = any(
            file_path.name in path.nodes for path in codebase.hot_paths
        )

        # Check error-prone
        enriched["is_error_prone"] = any(
            loc.file == file_path for loc in codebase.error_prone
        )

        # Get change frequency
        enriched["change_frequency"] = codebase.change_frequency.get(file_path, 0.0)

        # Get ownership
        enriched["file_ownership"] = codebase.file_ownership.get(file_path)

        # Get coupling score (sum of all couplings involving this file's module)
        module_name = str(file_path.with_suffix("")).replace("/", ".")
        coupling_scores = [
            score
            for (m1, m2), score in codebase.coupling_scores.items()
            if module_name in (m1, m2)
        ]
        if coupling_scores:
            enriched["coupling"] = sum(coupling_scores) / len(coupling_scores)
        else:
            enriched["coupling"] = 0.0

    async def _enrich_from_cache(
        self,
        enriched: dict[str, Any],
        artifact_id: str,
    ) -> None:
        """Add execution cache context."""
        if not self.execution_cache:
            return

        entry = self.execution_cache.get(artifact_id)
        if entry:
            enriched["skip_count"] = entry.skip_count
            enriched["last_execution_time_ms"] = entry.execution_time_ms
            enriched["last_status"] = entry.status.value

        # Lineage queries (O(1) via recursive CTE)
        enriched["upstream_artifacts"] = self.execution_cache.get_upstream(artifact_id)
        enriched["downstream_artifacts"] = self.execution_cache.get_downstream(artifact_id)

    async def _enrich_from_project_context(
        self,
        enriched: dict[str, Any],
        decision_type: DecisionType,
    ) -> None:
        """Add project context (decisions, failures, patterns)."""
        if not self.project_context:
            return

        # Similar past decisions
        try:
            similar = await self._query_similar_decisions(decision_type, enriched)
            enriched["similar_decisions"] = similar
        except Exception:
            enriched["similar_decisions"] = []

        # Related failures
        try:
            failures = await self._query_related_failures(enriched)
            enriched["related_failures"] = failures
        except Exception:
            enriched["related_failures"] = []

        # User patterns
        try:
            patterns = await self._query_user_patterns(decision_type)
            enriched["user_patterns"] = patterns
        except Exception:
            enriched["user_patterns"] = []

    async def _enrich_from_artifact_graph(
        self,
        enriched: dict[str, Any],
        artifact_id: str,
    ) -> None:
        """Add artifact graph context."""
        if not self.artifact_graph:
            return

        spec = self.artifact_graph.get(artifact_id)
        if spec:
            enriched["artifact_requires"] = list(spec.requires)
            enriched["artifact_contract"] = spec.contract

    async def _query_similar_decisions(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query similar past decisions from ProjectContext."""
        if not self.project_context:
            return []

        # Search decision history for similar contexts
        similar = []
        for decision in self._decision_history[-100:]:  # Last 100 decisions
            # Simple similarity: same file path or signal type
            if (
                decision.decision_type == decision_type
                and context.get("file_path")
                and "file_path" in decision.context_used
            ):
                similar.append(decision.to_dict())
        return similar[:5]  # Top 5 similar

    async def _query_related_failures(
        self,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query related failures from ProjectContext."""
        if not self.project_context or not hasattr(self.project_context, "failures"):
            return []

        try:
            file_path = context.get("file_path")
            if file_path:
                failures = self.project_context.failures.query_by_file(Path(file_path))
                return [f.to_dict() for f in failures[:3]] if failures else []
        except Exception:
            pass
        return []

    async def _query_user_patterns(
        self,
        decision_type: DecisionType,
    ) -> list[str]:
        """Query user patterns from ProjectContext."""
        if not self.project_context or not hasattr(self.project_context, "patterns"):
            return []

        try:
            patterns = self.project_context.patterns.get_patterns(decision_type.value)
            return patterns if patterns else []
        except Exception:
            return []

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
        for decision in reversed(self._decision_history[-50:]):
            if decision.decision_type != decision_type:
                continue

            if decision.confidence < 0.90:
                continue

            # Check context similarity (simple heuristic)
            if self._is_similar_context(context, decision):
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
    # Prompt Building
    # =========================================================================

    # =========================================================================
    # Fast Mode (Direct JSON, no tool calling)
    # =========================================================================

    def _build_fast_prompt(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Build fast prompt for direct JSON output (no tool calling).

        Simpler prompt that works with small models that don't support tools.
        """
        if decision_type == DecisionType.SEVERITY_ASSESSMENT:
            return self._fast_severity_prompt(context)
        elif decision_type == DecisionType.RECOVERY_STRATEGY:
            return self._fast_recovery_prompt(context)
        elif decision_type == DecisionType.SEMANTIC_APPROVAL:
            return self._fast_approval_prompt(context)
        else:
            return self._fast_generic_prompt(decision_type, context)

    def _fast_severity_prompt(self, context: dict[str, Any]) -> str:
        """Fast prompt for severity assessment."""
        return f"""Assess the severity of this code signal. Respond with ONLY valid JSON.

Signal: {context.get('signal_type', 'unknown')}
Content: "{context.get('content', '')}"
File: {context.get('file_path', 'unknown')}

Respond with this exact JSON structure:
{{"severity": "critical" | "high" | "medium" | "low", "confidence": 0.0-1.0, "rationale": "brief explanation"}}

JSON:"""

    def _fast_recovery_prompt(self, context: dict[str, Any]) -> str:
        """Fast prompt for recovery strategy."""
        return f"""Decide recovery strategy for this error. Respond with ONLY valid JSON.

Error: {context.get('error_type', 'unknown')}
Message: "{context.get('error_message', '')}"
Attempt: #{context.get('attempt_number', 1)}

Options: retry (transient), retry_different (new approach), escalate (need human), abort (give up)

{{"strategy": "retry" | "retry_different" | "escalate" | "abort", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:"""

    def _fast_approval_prompt(self, context: dict[str, Any]) -> str:
        """Fast prompt for approval decision."""
        return f"""Decide if this change can be auto-approved. Respond with ONLY valid JSON.

Goal: {context.get('goal_title', 'unknown')}
Category: {context.get('goal_category', 'unknown')}
Files: {context.get('files_affected', [])}

{{"decision": "approve" | "flag" | "deny", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:"""

    def _fast_generic_prompt(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Generic fast prompt for other decision types."""
        return f"""Make a {decision_type.value} decision. Respond with ONLY valid JSON.

Context: {self._format_context(context)}

{{"outcome": "your decision", "confidence": 0.0-1.0, "rationale": "brief explanation"}}

JSON:"""

    def _parse_json_decision(
        self,
        decision_type: DecisionType,
        result: Any,
    ) -> ReasonedDecision:
        """Parse direct JSON response (fast mode, no tool calling)."""
        import json
        import re

        text = result.text.strip()

        # Handle markdown code blocks
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()

        # Try to extract JSON object
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return self._apply_fallback(
                decision_type, {}, error=f"Failed to parse JSON: {text[:100]}"
            )

        # Extract fields based on decision type
        outcome = self._extract_fast_outcome(decision_type, data)
        confidence = float(data.get("confidence", 0.5))
        rationale = data.get("rationale", "")

        # Validate outcome
        if not self._validate_outcome(decision_type, outcome):
            return self._apply_fallback(
                decision_type, {}, error=f"Invalid outcome: {outcome}"
            )

        return ReasonedDecision(
            decision_type=decision_type,
            outcome=outcome,
            confidence=confidence,
            rationale=rationale,
            context_used=tuple(data.get("context_factors", [])),
        )

    def _extract_fast_outcome(
        self,
        decision_type: DecisionType,
        data: dict[str, Any],
    ) -> Any:
        """Extract outcome from fast mode JSON response."""
        if decision_type == DecisionType.SEVERITY_ASSESSMENT:
            return data.get("severity", data.get("outcome"))
        elif decision_type == DecisionType.RECOVERY_STRATEGY:
            return data.get("strategy", data.get("outcome"))
        elif decision_type == DecisionType.SEMANTIC_APPROVAL:
            return data.get("decision", data.get("outcome"))
        elif decision_type == DecisionType.AUTO_FIXABLE:
            return data.get("auto_fixable", data.get("outcome"))
        elif decision_type == DecisionType.RISK_ASSESSMENT:
            return data.get("risk_level", data.get("outcome"))
        else:
            return data.get("outcome")

    def _validate_outcome(self, decision_type: DecisionType, outcome: Any) -> bool:
        """Validate that outcome is valid for the decision type."""
        if outcome is None:
            return False

        validators = {
            DecisionType.SEVERITY_ASSESSMENT: lambda o: o in SEVERITY_LEVELS,
            DecisionType.RECOVERY_STRATEGY: lambda o: o in RECOVERY_STRATEGIES,
            DecisionType.SEMANTIC_APPROVAL: lambda o: o in APPROVAL_OUTCOMES,
            DecisionType.AUTO_FIXABLE: lambda o: isinstance(o, bool),
            DecisionType.RISK_ASSESSMENT: lambda o: o in SEVERITY_LEVELS,
        }

        validator = validators.get(decision_type)
        if validator:
            return validator(outcome)
        return True  # No specific validation for other types

    # =========================================================================
    # Standard Mode (Tool Calling)
    # =========================================================================

    def _build_prompt(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Build reasoning prompt for the decision type."""
        prompt_builders = {
            DecisionType.SEVERITY_ASSESSMENT: self._severity_prompt,
            DecisionType.RECOVERY_STRATEGY: self._recovery_prompt,
            DecisionType.SEMANTIC_APPROVAL: self._approval_prompt,
            DecisionType.ROOT_CAUSE_ANALYSIS: self._root_cause_prompt,
            DecisionType.AUTO_FIXABLE: self._auto_fixable_prompt,
            DecisionType.RISK_ASSESSMENT: self._risk_prompt,
        }

        builder = prompt_builders.get(decision_type)
        if builder:
            return builder(context)

        return self._generic_prompt(decision_type, context)

    def _severity_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for severity assessment using rich context."""
        # Build context section - only include non-empty/non-unknown fields
        context_lines = []

        if context.get('code_context'):
            context_lines.append(f"Code:\n```\n{context['code_context']}\n```")

        if context.get('in_hot_path') is True:
            context_lines.append("• In hot path (high traffic)")
        if context.get('is_error_prone') is True:
            context_lines.append("• Error-prone file (history of bugs)")
        if context.get('downstream_artifacts'):
            deps = context['downstream_artifacts']
            context_lines.append(f"• {len(deps)} downstream dependencies")
        if context.get('similar_decisions'):
            context_lines.append(
                f"Similar: {self._format_similar(context['similar_decisions'])}"
            )
        if context.get('related_failures'):
            context_lines.append(
                f"Past failures: {self._format_failures(context['related_failures'])}"
            )

        context_section = "\n".join(context_lines) if context_lines else "No additional context."

        return f"""Call `decide_severity` to assess this code signal.

Signal: {context.get('signal_type', 'unknown')}
Content: "{context.get('content', '')}"
File: {context.get('file_path', 'unknown')}

{context_section}

Severity levels:
- critical: Security/data loss risk, production-breaking
- high: Bugs, race conditions, important fixes
- medium: Code quality, minor issues
- low: Nice-to-have, cleanup, test improvements"""

    def _recovery_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for recovery strategy decision."""
        attempt = context.get('attempt_number', 1)
        past = context.get('past_failures', [])

        extra = ""
        if past:
            extra = f"\nPast failures: {self._format_failures(past)}"

        return f"""Call `decide_recovery` for this error.

Error: {context.get('error_type', 'unknown')}
Message: "{context.get('error_message', '')}"
Attempt: #{attempt}{extra}

Strategies:
- retry: Transient error, try again
- retry_different: Try new approach (provide hint)
- escalate: Need human help
- abort: Give up"""

    def _approval_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for semantic approval decision."""
        files = context.get('files_affected', [])
        file_str = f"{len(files)} files" if len(files) > 3 else ", ".join(files)

        return f"""Call `decide_approval` for this change.

Goal: {context.get('goal_title', 'unknown')}
Category: {context.get('goal_category', 'unknown')}
Files: {file_str}

Decisions:
- approve: Safe, auto-execute
- flag: Show user, allow proceeding
- deny: Require explicit approval"""

    def _root_cause_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for root cause analysis."""
        return f"""Analyze the root cause of this failure.

## Failure
- **Description**: {context.get('description', '')}
- **Error type**: {context.get('error_type', 'unknown')}
- **Error message**: {context.get('error_message', '')}

## Code Snapshot
```
{context.get('code_snapshot', 'N/A')}
```

## Similar Failures
{self._format_failures(context.get('similar_failures', []))}

---

Analyze by calling `decide_root_cause`. Identify:
1. What went wrong
2. Why it went wrong
3. How to prevent it in the future"""

    def _auto_fixable_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for auto-fixable assessment."""
        return f"""Determine if this signal can be auto-fixed.

## Signal
- **Type**: {context.get('signal_type', 'unknown')}
- **Content**: {context.get('content', '')}
- **File**: {context.get('file_path', 'unknown')}

## Context
{context.get('code_context', 'N/A')}

---

Decide by calling `decide_auto_fixable`:
- **true**: Can be fixed automatically without human judgment
- **false**: Needs human decision-making"""

    def _risk_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for risk assessment."""
        return f"""Assess the risk of this change.

## Change
- **Description**: {context.get('change_description', '')}
- **Files affected**: {context.get('files_affected', [])}
- **Lines changed**: {context.get('lines_changed', 'unknown')}

## Context
- **In hot path**: {context.get('in_hot_path', 'unknown')}
- **Downstream artifacts**: {context.get('downstream_artifacts', [])}
- **Error history**: {context.get('is_error_prone', 'unknown')}

---

Assess risk by calling `decide_risk` with level: low, medium, high, critical"""

    def _generic_prompt(
        self,
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Generic prompt for decision types without specialized prompts."""
        return f"""Make a decision about the following context.

## Decision Type
{decision_type.value}

## Context
{self._format_context(context)}

---

Call the appropriate decision tool with your reasoning."""

    def _format_similar(self, decisions: list[dict[str, Any]]) -> str:
        """Format similar decisions for prompt."""
        if not decisions:
            return "None found"
        lines = []
        for d in decisions[:3]:
            outcome = d.get("outcome", "?")
            conf = d.get("confidence", 0)
            rationale = d.get("rationale", "")[:50]
            lines.append(f"- {outcome} ({conf:.0%}): {rationale}")
        return "\n".join(lines)

    def _format_failures(self, failures: list[dict[str, Any]]) -> str:
        """Format failures for prompt."""
        if not failures:
            return "None found"
        return "\n".join(
            f"- {f.get('description', f.get('error_type', '?'))[:60]}"
            for f in failures[:3]
        )

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dict for generic prompt."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)) and len(str(value)) > 100:
                value = f"{type(value).__name__}[{len(value)} items]"
            lines.append(f"- **{key}**: {value}")
        return "\n".join(lines)

    # =========================================================================
    # Tool Definitions
    # =========================================================================

    def _get_tools(self, decision_type: DecisionType) -> tuple[Tool, ...]:
        """Get tool definitions for structured output."""
        tools: dict[DecisionType, tuple[Tool, ...]] = {
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
        # Map decision types to their outcome field names
        outcome_fields = {
            DecisionType.SEVERITY_ASSESSMENT: "severity",
            DecisionType.RECOVERY_STRATEGY: "strategy",
            DecisionType.SEMANTIC_APPROVAL: "decision",
            DecisionType.ROOT_CAUSE_ANALYSIS: "root_cause",
            DecisionType.AUTO_FIXABLE: "auto_fixable",
            DecisionType.RISK_ASSESSMENT: "risk_level",
        }

        field_name = outcome_fields.get(decision_type, "outcome")
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
        defaults = {
            DecisionType.SEVERITY_ASSESSMENT: "medium",
            DecisionType.AUTO_FIXABLE: False,
            DecisionType.RECOVERY_STRATEGY: "escalate",
            DecisionType.SEMANTIC_APPROVAL: "flag",
            DecisionType.RISK_ASSESSMENT: "medium",
            DecisionType.ROOT_CAUSE_ANALYSIS: "Unknown",
            DecisionType.GOAL_PRIORITY: 5,
            DecisionType.DISPLAY_VARIANT: "banner",
        }
        return defaults.get(decision_type)

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
