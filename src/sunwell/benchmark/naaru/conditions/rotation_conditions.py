"""Rotation condition implementations (H, I, K).

H/K: ROTATION - Single generation with thought rotation frames
I: ROTATION_LENS - Rotation with lens context
"""

import time
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.conditions.rotation import (
    DIVERGENT_ROTATION_FRAMES,
    ROTATION_FRAMES,
    build_rotation_prompt,
    parse_frame_usage,
)
from sunwell.benchmark.naaru.types import NaaruCondition, NaaruConditionOutput, RotationMetrics
from sunwell.models.protocol import GenerateOptions

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol


async def run_rotation(
    model: ModelProtocol,
    task: BenchmarkTask,
    divergent: bool = False,
) -> NaaruConditionOutput:
    """H/K: ROTATION - Single generation with thought rotation frames.

    Instead of multiple parallel generations + voting, uses a single generation
    with frame markers that prompt the model to shift perspectives mid-generation.

    This tests whether structured perspective shifting within one generation
    can achieve similar quality to Harmonic at lower token cost.

    Args:
        model: The model to use
        task: The benchmark task
        divergent: If True, use divergent frames (adversary/advocate/naive)
    """
    start_time = time.perf_counter()

    # Select frame set
    frames = DIVERGENT_ROTATION_FRAMES if divergent else ROTATION_FRAMES
    rotation_prompt = build_rotation_prompt(frames)

    # Single generation with rotation prompt
    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=rotation_prompt,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    # Parse frame usage from output
    frame_usage = parse_frame_usage(result.text, frames)

    condition = NaaruCondition.ROTATION_DIVERGENT if divergent else NaaruCondition.ROTATION

    return NaaruConditionOutput(
        condition=condition,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=rotation_prompt,
        rotation_metrics=RotationMetrics(
            frames_used=tuple(frame_usage.keys()),
            frame_token_counts=frame_usage,
            divergent_mode=divergent,
        ),
    )


async def run_rotation_lens(
    model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
    divergent: bool = False,
) -> NaaruConditionOutput:
    """I: ROTATION_LENS - Rotation with lens context.

    Combines thought rotation with lens heuristics for domain-specific
    perspective shifting.
    """
    start_time = time.perf_counter()

    # Build combined system prompt
    frames = DIVERGENT_ROTATION_FRAMES if divergent else ROTATION_FRAMES
    rotation_prompt = build_rotation_prompt(frames)
    lens_context = lens.to_context()

    combined_prompt = f"{lens_context}\n\n{rotation_prompt}"

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=combined_prompt,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    frame_usage = parse_frame_usage(result.text, frames)

    return NaaruConditionOutput(
        condition=NaaruCondition.ROTATION_LENS,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=combined_prompt,
        rotation_metrics=RotationMetrics(
            frames_used=tuple(frame_usage.keys()),
            frame_token_counts=frame_usage,
            divergent_mode=divergent,
        ),
    )
