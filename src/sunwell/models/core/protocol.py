"""Model protocol - provider-agnostic LLM interface.

Extended with tool calling support per RFC-012.
Includes LLM output sanitization per RFC-091.

Type definitions moved to sunwell.contracts.model; re-exported here
for backward compatibility.
"""

import logging
from typing import TYPE_CHECKING, Any

# Re-export all protocol types from contracts
from sunwell.contracts.model import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    Tool,
    ToolCall,
)

if TYPE_CHECKING:
    from sunwell.foundation.schema.models.skill import Skill

logger = logging.getLogger(__name__)


# =============================================================================
# LLM Output Sanitization (RFC-091) — stays here (business logic)
# =============================================================================


def sanitize_llm_content(text: str | None) -> str | None:
    """Remove control characters from LLM output.

    Preserves newlines, carriage returns, and tabs which are valid
    in JSON strings and needed for code formatting.

    Applied once at the model layer, not on every read.

    Args:
        text: Raw LLM output text (may be None for tool-only responses)

    Returns:
        Sanitized text with control characters removed, or None if input was None
    """
    if text is None:
        return None

    sanitized = "".join(c for c in text if not (ord(c) < 32 and c not in "\n\r\t"))

    # Log when sanitization actually removed characters (debug level)
    if len(sanitized) != len(text):
        logger.debug(
            "Sanitized control chars from LLM output",
            extra={
                "original_len": len(text),
                "sanitized_len": len(sanitized),
                "chars_removed": len(text) - len(sanitized),
            },
        )

    return sanitized


def _sanitize_dict_values(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize string values in a dict.

    Used for sanitizing tool call arguments which may contain control characters.

    Args:
        d: Dictionary with potentially unsanitized string values

    Returns:
        Dictionary with all string values sanitized
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = sanitize_llm_content(v)
        elif isinstance(v, dict):
            result[k] = _sanitize_dict_values(v)
        elif isinstance(v, list):
            result[k] = [
                _sanitize_dict_values(i)
                if isinstance(i, dict)
                else sanitize_llm_content(i)
                if isinstance(i, str)
                else i
                for i in v
            ]
        else:
            result[k] = v
    return result


def tool_from_skill(skill: "Skill") -> Tool:
    """Convert a Sunwell skill to a tool definition.

    This was previously ``Tool.from_skill()``.  Moved to a standalone
    function so that the ``Tool`` dataclass can live in contracts
    (stdlib-only).

    Args:
        skill: A Skill object with name, description, and optional parameters_schema

    Returns:
        A Tool object suitable for LLM function calling
    """
    return Tool(
        name=skill.name,
        description=skill.description,
        parameters=skill.parameters_schema if hasattr(skill, 'parameters_schema') and skill.parameters_schema else {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task to perform with this skill",
                }
            },
            "required": ["task"],
        },
    )
