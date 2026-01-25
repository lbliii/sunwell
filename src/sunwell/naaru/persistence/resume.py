"""Resume support for paused executions."""

import asyncio

from sunwell.naaru.executor import ArtifactResult, ExecutionResult
from sunwell.naaru.persistence.saved_execution import SavedExecution


async def resume_execution(
    execution: SavedExecution,
    create_fn,  # CreateArtifactFn
    on_progress=None,
) -> ExecutionResult:
    """Resume a paused or incomplete execution.

    Args:
        execution: The saved execution to resume
        create_fn: Function to create artifacts
        on_progress: Optional progress callback

    Returns:
        ExecutionResult with completed/failed artifacts
    """
    # Find completed wave
    completed_ids = execution.completed_ids
    waves = execution.graph.execution_waves()

    resume_from_wave = execution.get_resume_wave()

    if on_progress:
        on_progress(f"Resuming from wave {resume_from_wave + 1}/{len(waves)}")

    # Execute remaining waves
    result = ExecutionResult(
        completed={
            aid: ArtifactResult(
                artifact_id=aid,
                content=None,  # Content not preserved
                verified=comp.verified,
                model_tier=comp.model_tier,
                duration_ms=comp.duration_ms,
            )
            for aid, comp in execution.completed.items()
        },
        failed=dict(execution.failed),
    )

    for wave_num in range(resume_from_wave, len(waves)):
        wave = waves[wave_num]

        # Filter to incomplete artifacts in this wave
        to_execute = [aid for aid in wave if aid not in completed_ids]

        if not to_execute:
            continue

        if on_progress:
            on_progress(f"Wave {wave_num + 1}: {', '.join(to_execute)}")

        # Execute wave
        wave_results = await asyncio.gather(
            *[create_fn(execution.graph[aid]) for aid in to_execute],
            return_exceptions=True,
        )

        # Process results
        for artifact_id, wave_result in zip(to_execute, wave_results, strict=True):
            if isinstance(wave_result, Exception):
                result.failed[artifact_id] = str(wave_result)
            elif isinstance(wave_result, str):
                # create_fn returns string content
                artifact_result = ArtifactResult(
                    artifact_id=artifact_id,
                    content=wave_result,
                    verified=False,
                )
                result.completed[artifact_id] = artifact_result
            else:
                result.completed[artifact_id] = wave_result

    return result
