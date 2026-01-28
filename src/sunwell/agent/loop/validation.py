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
    from sunwell.agent.validation.gates import ValidationGate

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
            emit_hook_sync(
                HookEvent.GATE_FAIL,
                gate_id=gate.id,
                gate_type="syntax",
                files=file_paths,
                errors=error_messages,
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
        # Emit gate fail hook for exceptions
        emit_hook_sync(
            HookEvent.GATE_FAIL,
            gate_id=gate.id if 'gate' in locals() else "unknown",
            gate_type="syntax",
            files=file_paths,
            errors=[str(e)],
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

    from sunwell.agent.validation import Artifact
    from sunwell.agent.validation.gates import GateType, ValidationGate

    # Create artifacts for validation
    artifacts = [
        Artifact(path=Path(path), content="")  # Content loaded by validator
        for path in file_paths
    ]

    # Create contract validation gate
    gate = ValidationGate(
        id=f"contract_{protocol_name}",
        gate_type=GateType.CONTRACT,
        depends_on=(),
        validation=protocol_name,
        contract_protocol=protocol_name,
        contract_file=contract_file or "",
        timeout_s=60,
        description=f"Verify implementation satisfies {protocol_name}",
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
                yield AgentEvent(
                    EventType.CONTRACT_VERIFY_FAIL,
                    {
                        "task_id": "",
                        "protocol_name": protocol_name,
                        "final_tier": "gate",
                        "error_message": event.data.get("error_message", "Contract verification failed"),
                    },
                )
                emit_hook_sync(
                    HookEvent.GATE_FAIL,
                    gate_id=gate.id,
                    gate_type="contract",
                    files=file_paths,
                    protocol=protocol_name,
                    errors=[event.data.get("error_message", "Contract verification failed")],
                )

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
        emit_hook_sync(
            HookEvent.GATE_FAIL,
            gate_id=gate.id,
            gate_type="contract",
            files=file_paths,
            protocol=protocol_name,
            errors=[str(e)],
        )
