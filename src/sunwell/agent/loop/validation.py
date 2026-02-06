"""Validation gates for the agentic tool loop."""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    gate_start_event,
    gate_step_event,
    validate_error_event,
)
from sunwell.agent.hooks import HookEvent, emit_hook_sync

if TYPE_CHECKING:
    from sunwell.agent.validation import Artifact, ValidationStage

logger = logging.getLogger(__name__)


def create_artifacts_from_paths(file_paths: list[str]) -> list[Artifact]:
    """Create Artifact list from file paths for validation.

    Content is left empty as validators load it on demand.

    Args:
        file_paths: List of file path strings

    Returns:
        List of Artifact objects ready for validation
    """
    from sunwell.agent.validation import Artifact

    return [Artifact(path=Path(path), content="") for path in file_paths]


def emit_gate_failure(
    gate_id: str,
    gate_type: str,
    file_paths: list[str],
    errors: list[str],
) -> None:
    """Emit gate failure hook with consistent formatting.

    Args:
        gate_id: Unique gate identifier
        gate_type: Type of gate (syntax, contract, etc.)
        file_paths: Files that were validated
        errors: Error messages from validation
    """
    emit_hook_sync(
        HookEvent.GATE_FAIL,
        gate_id=gate_id,
        gate_type=gate_type,
        files=file_paths,
        errors=errors,
    )


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

    from sunwell.agent.validation import create_syntax_gate

    # Create artifacts for validation
    artifacts = create_artifacts_from_paths(file_paths)

    # Create validation gate for post-write checks
    gate = create_syntax_gate(
        id="post_tool_write",
        description="Post-write syntax validation",
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
        for step_result in gate_result.steps:
            yield gate_step_event(
                gate_id=gate.id,
                step=step_result.step,
                passed=step_result.passed,
                message=step_result.message or "",
            )

        # Emit hook events for gate pass/fail
        if gate_result.passed:
            emit_hook_sync(
                HookEvent.GATE_PASS,
                gate_id=gate.id,
                gate_type="syntax",
                files=file_paths,
            )
        else:
            # Emit error events
            error_messages = []
            for error in gate_result.errors:
                yield validate_error_event(
                    error_type="validation",
                    message=str(error),
                    file=error.file if hasattr(error, "file") else None,
                    line=error.line if hasattr(error, "line") else None,
                )
                error_messages.append(str(error))

            # Emit gate fail hook
            emit_gate_failure(gate.id, "syntax", file_paths, error_messages)

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
        # Emit gate fail hook for exceptions
        emit_gate_failure(
            gate.id if "gate" in locals() else "unknown",
            "syntax",
            file_paths,
            [str(e)],
        )
        # Don't fail the entire operation if validation has issues


async def run_contract_validation(
    file_paths: list[str],
    validation_stage: ValidationStage | None,
    protocol_name: str,
    contract_file: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """Run contract validation on implementation files (RFC-034).

    Verifies that implementation files satisfy their Protocol contract
    using tiered verification: AST → mypy → LLM.

    Args:
        file_paths: Paths to implementation files to verify
        validation_stage: Validation stage with runner
        protocol_name: Name of the Protocol to verify against
        contract_file: Optional path to file containing the Protocol

    Yields:
        AgentEvent for validation progress
    """
    if not validation_stage:
        logger.debug("Contract validation skipped - no validation stage configured")
        return

    if not protocol_name:
        logger.debug("Contract validation skipped - no protocol name provided")
        return

    logger.info(
        "═ CONTRACT VALIDATION → Verifying %d file(s) against %s",
        len(file_paths),
        protocol_name,
        extra={"files": file_paths, "protocol": protocol_name},
    )

    from sunwell.agent.validation import create_contract_gate

    # Create artifacts for validation
    artifacts = create_artifacts_from_paths(file_paths)

    # Create contract validation gate
    gate = create_contract_gate(
        id=f"contract_{protocol_name}",
        protocol_name=protocol_name,
        contract_file=contract_file or "",
    )

    # Emit gate start with contract-specific event
    yield AgentEvent(
        EventType.CONTRACT_VERIFY_START,
        {
            "task_id": "",
            "protocol_name": protocol_name,
            "implementation_file": file_paths[0] if file_paths else "",
            "contract_file": contract_file or "",
        },
    )

    try:
        # Run contract validation through the runner
        async for event in validation_stage.runner.validate_gate(gate, artifacts):
            yield event

            # Track if validation passed or failed
            if event.type == EventType.GATE_PASS:
                yield AgentEvent(
                    EventType.CONTRACT_VERIFY_PASS,
                    {
                        "task_id": "",
                        "protocol_name": protocol_name,
                        "final_tier": "gate",
                    },
                )
                emit_hook_sync(
                    HookEvent.GATE_PASS,
                    gate_id=gate.id,
                    gate_type="contract",
                    files=file_paths,
                    protocol=protocol_name,
                )
            elif event.type == EventType.GATE_FAIL:
                error_msg = event.data.get(
                    "error_message", "Contract verification failed"
                )
                yield AgentEvent(
                    EventType.CONTRACT_VERIFY_FAIL,
                    {
                        "task_id": "",
                        "protocol_name": protocol_name,
                        "final_tier": "gate",
                        "error_message": error_msg,
                    },
                )
                emit_gate_failure(gate.id, "contract", file_paths, [error_msg])

    except Exception as e:
        logger.warning("Contract validation error: %s", e)
        yield AgentEvent(
            EventType.CONTRACT_VERIFY_FAIL,
            {
                "task_id": "",
                "protocol_name": protocol_name,
                "final_tier": "error",
                "error_message": str(e),
            },
        )
        emit_gate_failure(gate.id, "contract", file_paths, [str(e)])
