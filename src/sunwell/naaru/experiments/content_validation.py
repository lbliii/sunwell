"""Signal-based content validation for generated artifacts.

Detects when generated content is wrong format and triggers escalation.

Example:
    # Check if generated Python file is actually Python
    signal = await validate_python_content(content, tiny_model)
    if signal == Trit.YES:  # Invalid
        # Escalate to larger model
        content = await regenerate_with_larger_model(task, large_model)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from sunwell.naaru.experiments.signals import Trit, trit_classify


class ContentType(Enum):
    """Expected content types for validation."""
    PYTHON = auto()
    JSON = auto()
    YAML = auto()
    MARKDOWN = auto()
    SQL = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of content validation."""
    is_valid: bool
    signal: Trit
    content_type: ContentType
    detected_type: ContentType
    issues: tuple[str, ...]

    @property
    def needs_escalation(self) -> bool:
        """Whether this should escalate to a larger model."""
        return self.signal == Trit.YES or (
            self.signal == Trit.MAYBE and len(self.issues) > 1
        )


def infer_expected_type(filename: str) -> ContentType:
    """Infer expected content type from filename."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    return {
        "py": ContentType.PYTHON,
        "json": ContentType.JSON,
        "yaml": ContentType.YAML,
        "yml": ContentType.YAML,
        "md": ContentType.MARKDOWN,
        "sql": ContentType.SQL,
    }.get(ext, ContentType.UNKNOWN)


def detect_content_type(content: str) -> ContentType:
    """Detect actual content type from content."""
    content = content.strip()

    # JSON detection
    if content.startswith("{") or content.startswith("["):
        try:
            import json
            json.loads(content)
            return ContentType.JSON
        except json.JSONDecodeError:
            pass

    # Python detection - look for Python-specific patterns
    python_patterns = [
        r"^(from|import)\s+\w+",  # imports
        r"^def\s+\w+\s*\(",       # function def
        r"^class\s+\w+",          # class def
        r"^@\w+",                 # decorators
        r"^if\s+__name__\s*==",   # main guard
    ]
    for pattern in python_patterns:
        if re.search(pattern, content, re.MULTILINE):
            return ContentType.PYTHON

    # YAML detection
    if re.match(r"^\w+:\s*\n", content) or content.startswith("---"):
        return ContentType.YAML

    # Markdown detection
    if content.startswith("#") or re.search(r"^\*\*\w+\*\*", content, re.MULTILINE):
        return ContentType.MARKDOWN

    # SQL detection
    sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE TABLE", "DROP"]
    if any(content.upper().startswith(kw) for kw in sql_keywords):
        return ContentType.SQL

    return ContentType.UNKNOWN


def validate_python_syntax(content: str) -> tuple[bool, list[str]]:
    """Check if content is valid Python syntax."""
    issues = []

    try:
        compile(content, "<string>", "exec")
        return True, []
    except SyntaxError as e:
        issues.append(f"SyntaxError: {e.msg} at line {e.lineno}")
        return False, issues


def fast_validate(content: str, expected_type: ContentType) -> ValidationResult:
    """Fast validation without LLM - uses heuristics.

    Returns:
        ValidationResult with signal:
        - NO (0): Content looks valid
        - MAYBE (1): Uncertain, might need LLM check
        - YES (2): Definitely invalid, needs regeneration
    """
    detected = detect_content_type(content)
    issues: list[str] = []

    # Type mismatch is a strong signal
    if expected_type != ContentType.UNKNOWN and detected != expected_type:
        issues.append(f"Expected {expected_type.name}, got {detected.name}")
        return ValidationResult(
            is_valid=False,
            signal=Trit.YES,  # Definite problem
            content_type=expected_type,
            detected_type=detected,
            issues=tuple(issues),
        )

    # Type-specific validation
    if expected_type == ContentType.PYTHON:
        syntax_valid, syntax_issues = validate_python_syntax(content)
        issues.extend(syntax_issues)

        if not syntax_valid:
            return ValidationResult(
                is_valid=False,
                signal=Trit.YES,  # Syntax error = definite problem
                content_type=expected_type,
                detected_type=detected,
                issues=tuple(issues),
            )

        # Check for stub/placeholder content
        if len(content.strip().splitlines()) < 3:
            issues.append("Content too short (likely placeholder)")
            return ValidationResult(
                is_valid=False,
                signal=Trit.MAYBE,
                content_type=expected_type,
                detected_type=detected,
                issues=tuple(issues),
            )

        # Check for "pass" only implementations
        if content.strip().endswith("pass") and content.count("pass") > content.count("def "):
            issues.append("Too many 'pass' statements (stub implementation)")
            return ValidationResult(
                is_valid=False,
                signal=Trit.MAYBE,
                content_type=expected_type,
                detected_type=detected,
                issues=tuple(issues),
            )

    # Looks valid
    return ValidationResult(
        is_valid=True,
        signal=Trit.NO,
        content_type=expected_type,
        detected_type=detected,
        issues=tuple(issues),
    )


async def validate_content_quality(
    content: str,
    expected_type: ContentType,
    task_description: str,
    model,
) -> ValidationResult:
    """Full validation with LLM for quality assessment.

    Use when fast_validate returns MAYBE or for high-stakes content.
    """
    # First do fast validation
    fast_result = fast_validate(content, expected_type)

    if fast_result.signal == Trit.YES:
        return fast_result  # Already know it's bad

    if fast_result.signal == Trit.NO and fast_result.is_valid:
        # Fast check says good, but do a quick LLM sanity check
        prompt = f"""Task: {task_description}
Expected: {expected_type.name} file

Content (first 500 chars):
{content[:500]}

Does this content fulfill the task correctly?
0: Yes, looks correct
1: Partially correct but incomplete
2: No, wrong format or doesn't match task

Respond with only 0, 1, or 2."""

        try:
            signal = await trit_classify(prompt, model)
            if signal != Trit.NO:
                issues = list(fast_result.issues) + ["LLM flagged potential issues"]
                return ValidationResult(
                    is_valid=signal == Trit.MAYBE,
                    signal=signal,
                    content_type=expected_type,
                    detected_type=fast_result.detected_type,
                    issues=tuple(issues),
                )
        except Exception:
            pass  # Fall through to fast result

    return fast_result


# =============================================================================
# Escalation Integration
# =============================================================================

async def validate_and_maybe_escalate(
    content: str,
    task_description: str,
    target_path: str,
    small_model,
    large_model,
    regenerate_fn,
) -> str:
    """Validate content and escalate to larger model if needed.

    Args:
        content: Generated content to validate
        task_description: What the content should do
        target_path: Filename for type inference
        small_model: Model for validation (tiny/cheap)
        large_model: Model for regeneration (larger/better)
        regenerate_fn: Async function to regenerate content with large model

    Returns:
        Validated (or regenerated) content
    """
    expected_type = infer_expected_type(target_path)

    # Fast validation first (no LLM cost)
    result = fast_validate(content, expected_type)

    if result.signal == Trit.NO:
        return content  # Looks good

    if result.signal == Trit.YES:
        # Definitely bad - escalate immediately
        return await regenerate_fn(large_model)

    # MAYBE - do LLM validation to decide
    full_result = await validate_content_quality(
        content, expected_type, task_description, small_model
    )

    if full_result.needs_escalation:
        return await regenerate_fn(large_model)

    return content
