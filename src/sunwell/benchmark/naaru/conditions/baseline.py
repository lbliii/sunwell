"""Baseline condition implementations (A, B).

A: BASELINE - Raw model capability
B: BASELINE_LENS - Lens context alone
"""

import time
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.types import NaaruCondition, NaaruConditionOutput
from sunwell.models.protocol import GenerateOptions

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol


async def run_baseline(
    model: ModelProtocol,
    task: BenchmarkTask,
) -> NaaruConditionOutput:
    """A: BASELINE - Raw model, no system prompt.

    This establishes the baseline capability of the model without any
    enhancement from Sunwell's techniques.
    """
    start_time = time.perf_counter()

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    return NaaruConditionOutput(
        condition=NaaruCondition.BASELINE,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt="",
    )


async def run_baseline_lens(
    model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
) -> NaaruConditionOutput:
    """B: BASELINE_LENS - Add lens context (no Naaru techniques).

    This isolates the effect of lens context alone without multi-persona
    or feedback loop enhancements.
    """
    start_time = time.perf_counter()

    # Build context from lens
    context = lens.to_context()

    result = await model.generate(
        task.prompt,
        options=GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=context,
        ),
    )

    elapsed = time.perf_counter() - start_time
    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4

    return NaaruConditionOutput(
        condition=NaaruCondition.BASELINE_LENS,
        output=result.text,
        tokens_used=tokens,
        time_seconds=elapsed,
        system_prompt=context,
    )
