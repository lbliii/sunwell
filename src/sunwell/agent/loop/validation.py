"""Validation gates for the agentic tool loop."""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from sunwell.agent.events import (
    AgentEvent,
    gate_start_event,
    gate_step_event,
    validate_error_event,
)

if TYPE_CHECKING:
    from sunwell.agent.validation import ValidationStage

logger = logging.getLogger(__name__)


async def run_validation_gates(
    file_paths: list[str],
    validation_stage: ValidationStage | None,
) -> AsyncIterator[AgentEvent]:
    """Run validation gates on written files (Sunwell differentiator).

    After each file write, runs syntax/lint validation. This catches
    errors early before they propagate - competitors don't do this.

    Args:
        file_paths: Paths of files that were written
        validation_stage: Validation stage to run gates

    Yields:
        AgentEvent for validation progress
    """
    if not validation_stage:
        logger.debug("Validation gates skipped - no validation stage configured")
        return

    logger.info(
        "═ VALIDATION GATES → Running syntax/lint on %d file(s)",
        len(file_paths),
        extra={"files": file_paths},
    )

    from sunwell.agent.validation import Artifact
    from sunwell.agent.gates import ValidationGate

    # Create artifacts for validation
    artifacts = [
        Artifact(path=path, content="")  # Content loaded by validator
        for path in file_paths
    ]

    # Create validation gate for post-write checks
    gate = ValidationGate(
        id="post_tool_write",
        type="syntax",  # Start with syntax, can expand
        after_tasks=[],
    )

    # Emit gate start
    yield gate_start_event(
        gate_id=gate.id,
        gate_type="syntax",
        artifacts=[a.path for a in artifacts],
    )

    try:
        # Run validation
        gate_result = await validation_stage.run_gate(gate, artifacts)

        # Emit step events
        for step_result in gate_result.step_results:
            yield gate_step_event(
                gate_id=gate.id,
                step=step_result.step,
                passed=step_result.passed,
                message=step_result.message or "",
            )

        # If validation failed, emit error events
        if not gate_result.passed:
            for error in gate_result.errors:
                yield validate_error_event(
                    error_type="validation",
                    message=str(error),
                    file=error.file if hasattr(error, "file") else None,
                    line=error.line if hasattr(error, "line") else None,
                )

            # Log for telemetry
            logger.warning(
                "Validation gate failed after tool write",
                extra={
                    "files": file_paths,
                    "errors": len(gate_result.errors),
                },
            )

    except Exception as e:
        logger.warning("Validation gate error: %s", e)
        # Don't fail the entire operation if validation has issues
