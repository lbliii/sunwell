"""Self-healing context builder (RFC-125).

Builds rich context for the agent to course-correct after failures.
Provides everything the model needs to fix issues without losing
the good work already done.

Example:
    >>> from sunwell.recovery import build_healing_context
    >>>
    >>> context = build_healing_context(recovery_state)
    >>> print(context)  # Rich markdown with errors, history, suggestions
"""

from sunwell.recovery.types import RecoveryState


def build_healing_context(
    state: RecoveryState,
    user_hint: str | None = None,
) -> str:
    """Build rich context for agent to self-heal.

    Provides:
    - What succeeded and why
    - What failed with exact errors
    - What was attempted before
    - Suggested fixes based on error patterns
    - Optional user hint

    Args:
        state: Recovery state with all artifacts and errors
        user_hint: Optional hint from user to guide fixes

    Returns:
        Markdown-formatted context string for agent
    """
    sections = [
        _build_header(state),
        _build_goal_section(state),
        _build_passed_section(state),
        _build_failed_section(state),
        _build_error_details(state),
        _build_fix_history(state),
        _build_suggestions(state),
    ]

    if user_hint:
        sections.append(_build_hint_section(user_hint))

    sections.append(_build_instructions(state))

    return "\n\n".join(s for s in sections if s)


def _build_header(state: RecoveryState) -> str:
    """Build context header."""
    return f"""## 🔄 Recovery Context

**Run ID**: {state.run_id}
**Status**: {state.summary}
**Reason**: {state.failure_reason or "Unknown"}"""


def _build_goal_section(state: RecoveryState) -> str:
    """Build goal section."""
    return f"""### Original Goal

{state.goal}"""


def _build_passed_section(state: RecoveryState) -> str:
    """Build section for passed artifacts."""
    passed = state.passed_artifacts
    if not passed:
        return ""

    lines = ["### ✅ What Succeeded", ""]
    lines.append("These artifacts passed validation. **Do not regenerate them.**")
    lines.append("")

    for artifact in passed:
        lines.append(f"- `{artifact.path}` — passed all gates")

    return "\n".join(lines)


def _build_failed_section(state: RecoveryState) -> str:
    """Build section for failed artifacts."""
    failed = state.failed_artifacts
    if not failed:
        return ""

    lines = ["### ⚠️ What Failed", ""]
    lines.append("These artifacts need fixes:")
    lines.append("")

    for artifact in failed:
        lines.append(f"**`{artifact.path}`**")
        if artifact.errors:
            for err in artifact.errors[:5]:  # Limit to 5
                lines.append(f"  - {err}")
            if len(artifact.errors) > 5:
                lines.append(f"  - ... and {len(artifact.errors) - 5} more errors")
        lines.append("")

    return "\n".join(lines)


def _build_error_details(state: RecoveryState) -> str:
    """Build detailed error section."""
    if not state.error_details:
        return ""

    lines = ["### Error Details", ""]
    lines.append("```")
    for err in state.error_details[:20]:  # Limit to 20
        lines.append(err)
    if len(state.error_details) > 20:
        lines.append(f"... and {len(state.error_details) - 20} more errors")
    lines.append("```")

    return "\n".join(lines)


def _build_fix_history(state: RecoveryState) -> str:
    """Build section about previous fix attempts."""
    if not state.fix_attempts:
        return ""

    lines = ["### Previous Fix Attempts", ""]
    lines.append("These approaches were already tried:")
    lines.append("")

    for i, attempt in enumerate(state.fix_attempts[-3:], 1):  # Last 3
        lines.append(f"**Attempt {i}**: {attempt.get('approach', 'Unknown')}")
        if attempt.get("errors_after"):
            lines.append(f"  Result: Still had {len(attempt['errors_after'])} errors")
        lines.append("")

    return "\n".join(lines)


def _build_suggestions(state: RecoveryState) -> str:
    """Build suggested fixes based on error patterns."""
    suggestions = _analyze_errors(state)
    if not suggestions:
        return ""

    lines = ["### Suggested Approach", ""]
    for suggestion in suggestions:
        lines.append(f"- {suggestion}")

    return "\n".join(lines)


def _analyze_errors(state: RecoveryState) -> list[str]:
    """Analyze error patterns and suggest fixes."""
    suggestions = []
    all_errors = " ".join(state.error_details).lower()

    # Common patterns
    if "import" in all_errors and ("not found" in all_errors or "no module" in all_errors):
        suggestions.append(
            "Check import paths — some modules may not exist yet or have wrong paths"
        )

    if "syntax" in all_errors:
        suggestions.append("Fix syntax errors first — other errors may be cascading from these")

    if "indent" in all_errors:
        suggestions.append("Check indentation — Python is whitespace-sensitive")

    if "undefined" in all_errors or "not defined" in all_errors:
        suggestions.append("Ensure all referenced names are defined before use")

    if "type" in all_errors and ("incompatible" in all_errors or "expected" in all_errors):
        suggestions.append("Review type annotations — ensure types match actual values")

    if "missing" in all_errors and "argument" in all_errors:
        suggestions.append("Check function calls — some may be missing required arguments")

    # Dependency analysis
    waiting = state.waiting_artifacts
    if waiting:
        suggestions.append(
            f"Fix failed artifacts first — {len(waiting)} artifacts are blocked waiting on them"
        )

    return suggestions


def _build_hint_section(hint: str) -> str:
    """Build section for user-provided hint."""
    return f"""### 💡 User Hint

{hint}"""


def _build_instructions(state: RecoveryState) -> str:
    """Build final instructions for agent."""
    failed_paths = [str(a.path) for a in state.failed_artifacts]
    passed_paths = [str(a.path) for a in state.passed_artifacts]

    return f"""### Instructions

1. **Focus on fixing these files**: {', '.join(failed_paths) or 'None'}
2. **DO NOT regenerate these files** (they are correct): {', '.join(passed_paths) or 'None'}
3. **Read the error details carefully** — they tell you exactly what's wrong
4. **Fix the root cause** — don't just suppress errors
5. **Maintain consistency** with the passed artifacts (same style, same patterns)

After fixing, all files will be re-validated. If issues persist, more specific
guidance will be provided."""
