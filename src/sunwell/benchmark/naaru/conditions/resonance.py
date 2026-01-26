"""Resonance condition implementation (E).

E: RESONANCE - Harmonic + feedback loop (full judge)
"""

import re
import time
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic
from sunwell.benchmark.naaru.types import NaaruCondition, NaaruConditionOutput, ResonanceMetrics
from sunwell.foundation.utils import safe_json_loads
from sunwell.models import GenerateOptions

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.models import ModelProtocol


async def judge_output(
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    output: str,
) -> tuple[str, float, list[str], int]:
    """Judge an output using the judge model.

    Returns:
        Tuple of (verdict, score, issues, tokens_used)
    """
    judge_prompt = f"""You are an expert code/content reviewer. Evaluate this output:

TASK: {task.prompt[:500]}

OUTPUT:
```
{output[:2500]}
```

CRITERIA (score each):
1. CORRECTNESS (0-3): Does it solve the task correctly?
2. COMPLETENESS (0-3): Is it thorough and complete?
3. QUALITY (0-2): Is it well-written and clear?
4. REQUIREMENTS (0-2): Does it meet specific requirements?

Score >= 6 = approve.

Respond with ONLY JSON:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "verdict": "approve" or "reject"}}"""

    result = await judge_model.generate(
        judge_prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=500),
    )

    tokens = result.usage.total_tokens if result.usage else 100

    try:
        response_text = result.text

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            judge_result = safe_json_loads(json_match.group())
            return (
                judge_result.get("verdict", "reject"),
                float(judge_result.get("score", 5)),
                judge_result.get("issues", []),
                tokens,
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback
    return "approve", 6.0, [], tokens


async def refine_output(
    model: ModelProtocol,
    task: BenchmarkTask,
    current_output: str,
    issues: list[str],
    system_prompt: str = "",
) -> tuple[str, int]:
    """Refine an output based on feedback.

    Returns:
        Tuple of (refined_output, tokens_used)
    """
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "No specific issues"

    refine_prompt = f"""The following output needs improvement:

ORIGINAL TASK: {task.prompt[:300]}

CURRENT OUTPUT:
```
{current_output[:1500]}
```

ISSUES TO FIX:
{issues_text}

Write an IMPROVED version that fixes ALL the issues above.
Keep the same core approach but address the quality concerns.
Output only:"""

    result = await model.generate(
        refine_prompt,
        options=GenerateOptions(
            temperature=0.5,
            max_tokens=2048,
            system_prompt=system_prompt if system_prompt else None,
        ),
    )

    tokens = result.usage.total_tokens if result.usage else len(result.text) // 4
    return result.text, tokens


async def run_resonance(
    model: ModelProtocol,
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    max_attempts: int = 2,
) -> NaaruConditionOutput:
    """E: RESONANCE - Harmonic + feedback loop (full judge).

    Builds on HARMONIC by adding a feedback loop: if the judge rejects
    the output, refine based on feedback. Uses the full judge model
    (not tiered validation).
    """
    start_time = time.perf_counter()

    # First, run harmonic synthesis
    harmonic_result = await run_harmonic(model, task)

    total_tokens = harmonic_result.tokens_used
    current_output = harmonic_result.output

    # Run feedback loop
    initial_score = 0.0
    final_score = 0.0
    refinement_attempts = 0
    issues_addressed: list[str] = []

    for attempt in range(max_attempts):
        # Judge the current output
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
        refined_output, refine_tokens = await refine_output(
            model, task, current_output, issues
        )
        total_tokens += refine_tokens

        current_output = refined_output
        refinement_attempts += 1
        issues_addressed.extend(issues)
        final_score = score
    else:
        # Max attempts reached - get final score
        _, final_score, _, judge_tokens = await judge_output(
            judge_model, task, current_output
        )
        total_tokens += judge_tokens

    elapsed = time.perf_counter() - start_time

    return NaaruConditionOutput(
        condition=NaaruCondition.RESONANCE,
        output=current_output,
        tokens_used=total_tokens,
        time_seconds=elapsed,
        harmonic_metrics=harmonic_result.harmonic_metrics,
        resonance_metrics=ResonanceMetrics(
            refinement_attempts=refinement_attempts,
            initial_score=initial_score,
            final_score=final_score,
            issues_addressed=tuple(issues_addressed),
            escalated_to_full_judge=True,  # Always uses full judge in this condition
        ),
    )
