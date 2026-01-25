"""Event validation functions (RFC-060)."""

import logging
import os
from typing import Any

from sunwell.agent.events import AgentEvent, EventType

from .registry import REQUIRED_FIELDS

# RFC-060: Validation mode control via environment variable
# Values: "strict" (raise on error), "lenient" (log warning), "off" (no validation)
# Default: "lenient" in production, can be set to "strict" for dev/CI
_VALIDATION_MODE_VAR = "SUNWELL_EVENT_VALIDATION"


def get_validation_mode() -> str:
    """Get the current event validation mode.

    RFC-060: Controlled via SUNWELL_EVENT_VALIDATION environment variable.

    Returns:
        "strict" - Raise ValueError on validation failure
        "lenient" - Log warning but emit event anyway (default)
        "off" - No validation
    """
    return os.environ.get(_VALIDATION_MODE_VAR, "lenient").lower()


def validate_event_data(event_type: EventType, data: dict[str, Any]) -> dict[str, Any]:
    """Validate event data against schema.

    Args:
        event_type: The event type
        data: Event data to validate

    Returns:
        Validated and normalized data

    Raises:
        ValueError: If required fields are missing (only in strict mode)
    """
    # Normalize field names (artifact_id → task_id)
    normalized = dict(data)

    # Map artifact_id to task_id for compatibility
    if "artifact_id" in normalized and "task_id" not in normalized:
        normalized["task_id"] = normalized["artifact_id"]

    # Check required fields
    required = REQUIRED_FIELDS.get(event_type, set())
    missing = required - set(normalized.keys())

    if missing:
        error_msg = (
            f"Event {event_type.value} missing required fields: {missing}. "
            f"Got: {list(normalized.keys())}"
        )
        mode = get_validation_mode()
        if mode == "strict":
            raise ValueError(error_msg)
        elif mode == "lenient":
            logging.warning(f"[RFC-060] Event validation warning: {error_msg}")
        # mode == "off": silently continue

    return normalized


def create_validated_event(
    event_type: EventType,
    data: dict[str, Any],
    **kwargs: Any,
) -> AgentEvent:
    """Create an AgentEvent with validated data.

    RFC-060: Validation behavior controlled by SUNWELL_EVENT_VALIDATION env var.
    - "strict": Raise ValueError on validation failure
    - "lenient": Log warning but create event anyway (default)
    - "off": No validation

    Args:
        event_type: The event type
        data: Event data (will be validated)
        **kwargs: Additional data fields

    Returns:
        Validated AgentEvent

    Raises:
        ValueError: If validation fails and mode is "strict"
    """
    merged_data = {**data, **kwargs}

    mode = get_validation_mode()
    if mode != "off":
        try:
            validated_data = validate_event_data(event_type, merged_data)
        except ValueError:
            if mode == "strict":
                raise
            # lenient mode: use unvalidated data
            validated_data = merged_data
    else:
        validated_data = merged_data

    return AgentEvent(event_type, validated_data)
