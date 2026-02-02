"""Tool calling reliability detection.

Detects when a model fails to properly use tools, which can indicate:
1. Model doesn't support tool calling well
2. Tool emulation isn't working
3. Model is hallucinating task completion

This enables sunwell to:
- Warn users about unreliable tool calling
- Retry with different strategies
- Fall back to more capable models
- Collect metrics on model reliability
"""

import re
from dataclasses import dataclass
from enum import Enum

class ToolFailureType(Enum):
    """Types of tool calling failures."""

    NONE = "none"  # No failure detected

    # Model didn't call tools when it should have
    NO_TOOLS_WHEN_NEEDED = "no_tools_when_needed"

    # Model called tool with invalid/empty arguments
    INVALID_TOOL_ARGS = "invalid_tool_args"

    # Model response suggests task completion without tool calls
    HALLUCINATED_COMPLETION = "hallucinated_completion"

    # Tool emulation failed to parse tool calls from response
    EMULATION_PARSE_FAILURE = "emulation_parse_failure"


@dataclass(frozen=True, slots=True)
class ToolReliabilityResult:
    """Result of tool calling reliability check."""

    failure_type: ToolFailureType
    confidence: float  # 0.0-1.0 confidence in the detection
    message: str
    suggested_action: str | None = None


# Phrases that suggest task completion (hallucination indicators)
_COMPLETION_PHRASES = (
    # Past tense completion claims
    r"i('ve| have) (added|created|updated|fixed|done|completed|written|saved|made|built)",
    r"i (just )?(added|created|updated|fixed|wrote|made|built|finished|completed)",
    r"successfully (added|created|updated|fixed|wrote|completed|built|made|finished)",
    # Direct completion claims
    r"done!",
    r"all (done|set|finished)",
    r"(task|request|job|work) (is )?(complete|done|finished)",
    r"(here's|here is) (the|your) (file|code|result|output)",
    # Affirmative completion
    r"i've finished",
    r"ready to use",
    r"task completed",
    r"it's done",
    r"that's done",
    r"finished!",
    r"complete!",
    r"all set!",
    # Offering result
    r"here (is|are) (the|your)",
    r"(i've|i have) (finished|completed|done) (the|your|this)",
)

# Phrases that suggest refusal or inability to act
_REFUSAL_PHRASES = (
    r"i (can't|cannot|can not|am unable to)",
    r"i('m| am) sorry,? (but )?i (can't|cannot|can not)",
    r"unfortunately,? i (can't|cannot|can not)",
    r"i('d| would) need (more|additional) (information|details|context)",
    r"please provide (more|additional)",
    r"could you (please )?(provide|give|share|tell)",
    r"i('ll| will) need you to",
    r"none of the available (tools|functions)",
)

_COMPLETION_PATTERN = re.compile(
    "|".join(_COMPLETION_PHRASES),
    re.IGNORECASE,
)

_REFUSAL_PATTERN = re.compile(
    "|".join(_REFUSAL_PHRASES),
    re.IGNORECASE,
)


def detect_tool_failure(
    *,
    is_action_context: bool,
    needs_tools: bool,
    tool_calls_total: int,
    response_text: str | None,
    tools_available: int,
) -> ToolReliabilityResult:
    """Detect if tool calling failed in a suspicious way.

    Args:
        is_action_context: Whether we're in an action context (tools expected)
        needs_tools: Whether signals indicated tools were needed
        tool_calls_total: Total tool calls made during execution
        response_text: The model's final response text
        tools_available: Number of tools that were available

    Returns:
        ToolReliabilityResult with failure type and details
    """
    is_action = is_action_context

    # Case 1: Action intent + needs_tools=YES + no tools called
    if is_action and needs_tools and tool_calls_total == 0:
        # Check if response suggests completion (hallucination)
        if response_text and _COMPLETION_PATTERN.search(response_text):
            return ToolReliabilityResult(
                failure_type=ToolFailureType.HALLUCINATED_COMPLETION,
                confidence=0.9,
                message=(
                    "Model claimed task completion without calling any tools. "
                    "Response suggests completion but tool_calls_total=0."
                ),
                suggested_action=(
                    "Consider using a model with native tool support, "
                    "or retry with tool_choice='required'."
                ),
            )

        # Check if response shows refusal to act
        if response_text and _REFUSAL_PATTERN.search(response_text):
            return ToolReliabilityResult(
                failure_type=ToolFailureType.NO_TOOLS_WHEN_NEEDED,
                confidence=0.85,
                message=(
                    "Model refused to act or asked for clarification instead of using tools. "
                    f"Tools available: {tools_available}."
                ),
                suggested_action=(
                    "Model may need more explicit instructions to use tools proactively."
                ),
            )

        # No completion/refusal phrases, but still suspicious
        return ToolReliabilityResult(
            failure_type=ToolFailureType.NO_TOOLS_WHEN_NEEDED,
            confidence=0.7,
            message=(
                f"Task required tools (needs_tools=YES) but no tools were called. "
                f"Tools available: {tools_available}."
            ),
            suggested_action="Check if model supports tool calling.",
        )

    # Case 2: Tools available but conversation-style response for an action
    if (
        is_action
        and tools_available > 0
        and tool_calls_total == 0
        and response_text
    ):
        # Check for hallucinated completion
        if _COMPLETION_PATTERN.search(response_text):
            return ToolReliabilityResult(
                failure_type=ToolFailureType.HALLUCINATED_COMPLETION,
                confidence=0.6,
                message=(
                    "Task intent with tools available but model responded "
                    "conversationally with completion phrases."
                ),
                suggested_action="Model may not follow tool-calling instructions well.",
            )

        # Check for refusal
        if _REFUSAL_PATTERN.search(response_text):
            return ToolReliabilityResult(
                failure_type=ToolFailureType.NO_TOOLS_WHEN_NEEDED,
                confidence=0.65,
                message=(
                    "Task intent but model asked for clarification or refused "
                    "instead of using available tools."
                ),
                suggested_action="Model may be overly cautious about using tools.",
            )

    # No failure detected
    return ToolReliabilityResult(
        failure_type=ToolFailureType.NONE,
        confidence=1.0,
        message="Tool calling appears to have worked correctly.",
    )


def detect_blocked_tool_pattern(
    blocked_tools: list[tuple[str, str]],  # [(tool_name, reason), ...]
    tool_calls_total: int,
    response_text: str | None,
) -> ToolReliabilityResult | None:
    """Detect if blocked tool calls led to hallucination.

    When tools are blocked (e.g., for empty arguments), the model might
    just give up and hallucinate completion instead of retrying.

    Args:
        blocked_tools: List of (tool_name, block_reason) tuples
        tool_calls_total: Successful tool calls after blocks
        response_text: Final response text

    Returns:
        ToolReliabilityResult if suspicious pattern detected, None otherwise
    """
    if not blocked_tools:
        return None

    # Blocked tools + no successful calls + completion phrases = suspicious
    if (
        tool_calls_total == 0
        and response_text
        and _COMPLETION_PATTERN.search(response_text)
    ):
        tool_names = [t[0] for t in blocked_tools]
        return ToolReliabilityResult(
            failure_type=ToolFailureType.INVALID_TOOL_ARGS,
            confidence=0.85,
            message=(
                f"Model tried to call {tool_names} but was blocked, "
                f"then claimed completion without successful tool calls."
            ),
            suggested_action=(
                "Model may not understand tool argument requirements. "
                "Consider providing more explicit tool descriptions."
            ),
        )

    return None
