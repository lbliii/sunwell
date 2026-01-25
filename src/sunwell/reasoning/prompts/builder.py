"""Prompt builder for reasoned decisions (RFC-073)."""

import re
from typing import Any

from sunwell.reasoning.decisions import DecisionType

# Pre-compiled regex patterns
_MARKDOWN_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


class PromptBuilder:
    """Builds prompts for reasoned decisions.

    Supports both fast mode (direct JSON) and standard mode (tool calling).
    """

    @staticmethod
    def build_fast_prompt(
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Build fast prompt for direct JSON output (no tool calling).

        Simpler prompt that works with small models that don't support tools.
        """
        if decision_type == DecisionType.SEVERITY_ASSESSMENT:
            return PromptBuilder._fast_severity_prompt(context)
        elif decision_type == DecisionType.RECOVERY_STRATEGY:
            return PromptBuilder._fast_recovery_prompt(context)
        elif decision_type == DecisionType.SEMANTIC_APPROVAL:
            return PromptBuilder._fast_approval_prompt(context)
        else:
            return PromptBuilder._fast_generic_prompt(decision_type, context)

    @staticmethod
    def _fast_severity_prompt(context: dict[str, Any]) -> str:
        """Fast prompt for severity assessment."""
        return f"""Assess the severity of this code signal. Respond with ONLY valid JSON.

Signal: {context.get('signal_type', 'unknown')}
Content: "{context.get('content', '')}"
File: {context.get('file_path', 'unknown')}

Respond with this exact JSON structure:
{{"severity": "critical" | "high" | "medium" | "low", "confidence": 0.0-1.0, "rationale": "brief explanation"}}

JSON:"""

    @staticmethod
    def _fast_recovery_prompt(context: dict[str, Any]) -> str:
        """Fast prompt for recovery strategy."""
        return f"""Decide recovery strategy for this error. Respond with ONLY valid JSON.

Error: {context.get('error_type', 'unknown')}
Message: "{context.get('error_message', '')}"
Attempt: #{context.get('attempt_number', 1)}

Options: retry (transient), retry_different (new approach), escalate (need human), abort (give up)

{{"strategy": "retry" | "retry_different" | "escalate" | "abort", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:"""

    @staticmethod
    def _fast_approval_prompt(context: dict[str, Any]) -> str:
        """Fast prompt for approval decision."""
        return f"""Decide if this change can be auto-approved. Respond with ONLY valid JSON.

Goal: {context.get('goal_title', 'unknown')}
Category: {context.get('goal_category', 'unknown')}
Files: {context.get('files_affected', [])}

{{"decision": "approve" | "flag" | "deny", "confidence": 0.0-1.0, "rationale": "why"}}

JSON:"""

    @staticmethod
    def _fast_generic_prompt(
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Generic fast prompt for other decision types."""
        return f"""Make a {decision_type.value} decision. Respond with ONLY valid JSON.

Context: {PromptBuilder._format_context(context)}

{{"outcome": "your decision", "confidence": 0.0-1.0, "rationale": "brief explanation"}}

JSON:"""

    @staticmethod
    def build_prompt(
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Build reasoning prompt for the decision type (standard mode with tool calling)."""
        prompt_builders = {
            DecisionType.SEVERITY_ASSESSMENT: PromptBuilder._severity_prompt,
            DecisionType.RECOVERY_STRATEGY: PromptBuilder._recovery_prompt,
            DecisionType.SEMANTIC_APPROVAL: PromptBuilder._approval_prompt,
            DecisionType.ROOT_CAUSE_ANALYSIS: PromptBuilder._root_cause_prompt,
            DecisionType.AUTO_FIXABLE: PromptBuilder._auto_fixable_prompt,
            DecisionType.RISK_ASSESSMENT: PromptBuilder._risk_prompt,
        }

        builder = prompt_builders.get(decision_type)
        if builder:
            return builder(context)

        return PromptBuilder._generic_prompt(decision_type, context)

    @staticmethod
    def _severity_prompt(context: dict[str, Any]) -> str:
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
                f"Similar: {PromptBuilder._format_similar(context['similar_decisions'])}"
            )
        if context.get('related_failures'):
            context_lines.append(
                f"Past failures: {PromptBuilder._format_failures(context['related_failures'])}"
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

    @staticmethod
    def _recovery_prompt(context: dict[str, Any]) -> str:
        """Build prompt for recovery strategy decision."""
        attempt = context.get('attempt_number', 1)
        past = context.get('past_failures', [])

        extra = ""
        if past:
            extra = f"\nPast failures: {PromptBuilder._format_failures(past)}"

        return f"""Call `decide_recovery` for this error.

Error: {context.get('error_type', 'unknown')}
Message: "{context.get('error_message', '')}"
Attempt: #{attempt}{extra}

Strategies:
- retry: Transient error, try again
- retry_different: Try new approach (provide hint)
- escalate: Need human help
- abort: Give up"""

    @staticmethod
    def _approval_prompt(context: dict[str, Any]) -> str:
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

    @staticmethod
    def _root_cause_prompt(context: dict[str, Any]) -> str:
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
{PromptBuilder._format_failures(context.get('similar_failures', []))}

---

Analyze by calling `decide_root_cause`. Identify:
1. What went wrong
2. Why it went wrong
3. How to prevent it in the future"""

    @staticmethod
    def _auto_fixable_prompt(context: dict[str, Any]) -> str:
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

    @staticmethod
    def _risk_prompt(context: dict[str, Any]) -> str:
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

    @staticmethod
    def _generic_prompt(
        decision_type: DecisionType,
        context: dict[str, Any],
    ) -> str:
        """Generic prompt for decision types without specialized prompts."""
        return f"""Make a decision about the following context.

## Decision Type
{decision_type.value}

## Context
{PromptBuilder._format_context(context)}

---

Call the appropriate decision tool with your reasoning."""

    @staticmethod
    def _format_similar(decisions: list[dict[str, Any]]) -> str:
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

    @staticmethod
    def _format_failures(failures: list[dict[str, Any]]) -> str:
        """Format failures for prompt."""
        if not failures:
            return "None found"
        return "\n".join(
            f"- {f.get('description', f.get('error_type', '?'))[:60]}"
            for f in failures[:3]
        )

    @staticmethod
    def _format_context(context: dict[str, Any]) -> str:
        """Format context dict for generic prompt."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)) and len(str(value)) > 100:
                value = f"{type(value).__name__}[{len(value)} items]"
            lines.append(f"- **{key}**: {value}")
        return "\n".join(lines)

    @staticmethod
    def parse_json_decision(
        decision_type: DecisionType,
        result: Any,
        outcome_validators: dict[DecisionType, Any],
        conservative_defaults: dict[DecisionType, Any],
    ) -> tuple[Any, float, str]:
        """Parse direct JSON response (fast mode, no tool calling).

        Args:
            decision_type: Type of decision
            result: Model generation result
            outcome_validators: Validators for each decision type
            conservative_defaults: Default outcomes for fallback

        Returns:
            Tuple of (outcome, confidence, rationale)
        """
        import json

        text = result.text.strip()

        # Handle markdown code blocks
        if "```" in text:
            match = _MARKDOWN_CODE_BLOCK_RE.search(text)
            if match:
                text = match.group(1).strip()

        # Try to extract JSON object
        match = _JSON_OBJECT_RE.search(text)
        if match:
            text = match.group(0)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            outcome = conservative_defaults.get(decision_type)
            return outcome, 0.5, f"Failed to parse JSON: {text[:100]}"

        # Extract fields based on decision type
        outcome = PromptBuilder._extract_fast_outcome(decision_type, data)
        confidence = float(data.get("confidence", 0.5))
        rationale = data.get("rationale", "")

        # Validate outcome
        validator = outcome_validators.get(decision_type)
        if validator and not validator(outcome):
            outcome = conservative_defaults.get(decision_type)
            rationale = f"Invalid outcome, using default: {rationale}"

        return outcome, confidence, rationale

    @staticmethod
    def _extract_fast_outcome(
        decision_type: DecisionType,
        data: dict[str, Any],
    ) -> Any:
        """Extract outcome from fast mode JSON response."""
        outcome_fields = {
            DecisionType.SEVERITY_ASSESSMENT: "severity",
            DecisionType.RECOVERY_STRATEGY: "strategy",
            DecisionType.SEMANTIC_APPROVAL: "decision",
            DecisionType.AUTO_FIXABLE: "auto_fixable",
            DecisionType.RISK_ASSESSMENT: "risk_level",
        }
        field_name = outcome_fields.get(decision_type, "outcome")
        return data.get(field_name, data.get("outcome"))
