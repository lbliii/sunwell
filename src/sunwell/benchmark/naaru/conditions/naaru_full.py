"""Full Naaru condition implementations (F, G).

F: NAARU_FULL - Full Naaru with tiered validation
G: NAARU_FULL_LENS - Full Naaru + lens context
"""

import time
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic_lens
from sunwell.benchmark.naaru.conditions.resonance import judge_output, refine_output
from sunwell.benchmark.naaru.conditions.utils import lightweight_validate
from sunwell.benchmark.naaru.types import NaaruCondition, NaaruConditionOutput, ResonanceMetrics

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol

# Import run_harmonic for F condition
from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic


async def run_naaru_full(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """F: NAARU_FULL - Full Naaru with tiered validation.

    Same as RESONANCE but uses tiered validation (lightweight check first,
    escalate to full judge if uncertain). This tests cost savings from
    tiered validation.
    """
    start_time = time.perf_counter()

    # First, run harmonic synthesis
    harmonic_result = await run_harmonic(model, task)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop with tiered validation
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []
    escalated = False

    for attempt in range(max_attempts):
        # First try lightweight validation
        is_ok, lightweight_issues = lightweight_validate(task, current_output)

        if is_ok:
            # Approved by lightweight check - assign high score
            final_score = 8.0 if attempt == 0 else final_score
            if attempt == 0:
                initial_score = 8.0
            break

        # Lightweight check found issues - escalate to full judge
        escalated = True
        verdict, score, issues, judge_tokens = await judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

        if attempt == 0:
            initial_score = score

        if verdict == "approve" or score >= 7.0:
            final_score = score
            break

        # Refine based on feedback
        all_issues = list(set(lightweight_issues + issues))
        refined_output, refine_tokens = await refine_output(
            model, task, current_output, all_issues
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(all_issues)
        final_score = score

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.NAARU_FULL,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=escalated,
        ),
    )


async def run_naaru_full_lens(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    lens: Lens,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """G: NAARU_FULL_LENS - Full Naaru + lens context.

    The complete package: lens personas + harmonic synthesis + tiered
    validation + feedback loop. This is the condition we expect to
    perform best.
    """
    start_time = time.perf_counter()

    # First, run harmonic synthesis with lens personas
    harmonic_result = await run_harmonic_lens(model, task, lens)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop with tiered validation
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []
    escalated = False

    for attempt in range(max_attempts):
        # First try lightweight validation
        is_ok, lightweight_issues = lightweight_validate(task, current_output)

        if is_ok:
            final_score = 8.0 if attempt == 0 else final_score
            if attempt == 0:
                initial_score = 8.0
            break

        # Escalate to full judge
        escalated = True
        verdict, score, issues, judge_tokens = await judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

        if attempt == 0:
            initial_score = score

        if verdict == "approve" or score >= 7.0:
            final_score = score
            break

        # Refine with lens context
        all_issues = list(set(lightweight_issues + issues))
        lens_context = lens.to_context()
        refined_output, refine_tokens = await refine_output(
            model, task, current_output, all_issues, system_prompt=lens_context
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(all_issues)
        final_score = score

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.NAARU_FULL_LENS,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=escalated,
        ),
        system_prompt="[lens context used]",
    )
