"""LLM-as-Judge evaluation (Tier 2).

Pairwise comparison with position randomization and majority vote.
"""


import random
import re
from typing import TYPE_CHECKING

from sunwell.benchmark.types import (
    AggregatedVerdict,
    BenchmarkTask,
    DimensionScore,
    JudgeVerdict,
    Verdict,
)
from sunwell.foundation.utils import safe_json_loads
from sunwell.models import GenerateOptions, ModelProtocol

if TYPE_CHECKING:
    pass


# =============================================================================
# Judge Prompt Template
# =============================================================================

JUDGE_PROMPT_TEMPLATE = """You are a strict, impartial judge evaluating two responses to a documentation/code task.

## Task
{task_prompt}

## Response A
{output_a}

## Response B
{output_b}

## Evaluation Rubric
{rubric}

## Instructions
1. For each dimension, provide scores (1-10) for both A and B
2. Provide a one-sentence justification for each score difference
3. Determine overall winner: A, B, or TIE

Be strict but fair. Focus on concrete quality differences, not style preferences.

## Response Format (JSON)
{{
    "dimensions": [
        {{
            "dimension": "dimension_name",
            "score_a": 8,
            "score_b": 7,
            "justification": "One sentence explanation"
        }}
    ],
    "overall_winner": "A" | "B" | "TIE",
    "confidence": 0.85
}}

Respond ONLY with valid JSON, no markdown formatting."""


async def evaluate_with_judge(
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    output_a: str,
    output_b: str,
    num_runs: int = 3,
) -> AggregatedVerdict:
    """Tier 2: Pairwise LLM evaluation with position randomization.

    Runs multiple comparisons with randomized order and aggregates
    via majority vote to reduce position bias.
    """
    verdicts: list[JudgeVerdict] = []

    for _ in range(num_runs):
        # Randomize order to prevent position bias
        if random.random() > 0.5:
            first, second = output_a, output_b
            order = "ab"
        else:
            first, second = output_b, output_a
            order = "ba"

        verdict = await single_judge_call(
            judge_model=judge_model,
            task=task,
            first_output=first,
            second_output=second,
            order=order,
        )
        verdicts.append(verdict)

    return aggregate_verdicts(verdicts)


async def single_judge_call(
    judge_model: ModelProtocol,
    task: BenchmarkTask,
    first_output: str,
    second_output: str,
    order: str,
) -> JudgeVerdict:
    """Execute a single judge evaluation."""
    # Format rubric
    rubric_lines = []
    for dim in task.evaluation.rubric:
        rubric_lines.append(
            f"- **{dim.dimension}** (weight: {dim.weight}): {dim.criteria}"
        )
    rubric_text = "\n".join(rubric_lines) if rubric_lines else "Evaluate on accuracy, completeness, and usability."

    # Build prompt
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        task_prompt=task.prompt[:500],
        output_a=first_output[:2000],
        output_b=second_output[:2000],
        rubric=rubric_text,
    )

    # Call judge model
    result = await judge_model.generate(
        prompt,
        options=GenerateOptions(
            temperature=0.1,  # Low temperature for consistency
            max_tokens=1000,
        ),
    )

    # Parse response
    return parse_judge_response(result.text, order)


def parse_judge_response(response: str, order: str) -> JudgeVerdict:
    """Parse the judge's JSON response."""
    # Try to extract JSON from response
    try:
        # Handle potential markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        data = safe_json_loads(response)
    except ValueError:
        # Fallback: try to find JSON-like structure
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = safe_json_loads(response[json_start:json_end])
            else:
                raise ValueError("No JSON found")
        except ValueError:
            # Default to TIE if parsing fails
            return JudgeVerdict(
                winner=Verdict.TIE,
                dimension_scores=(),
                confidence=0.0,
                order=order,
                raw_response=response,
            )

    # Parse dimensions
    dimension_scores: list[DimensionScore] = []
    for dim in data.get("dimensions", []):
        dimension_scores.append(DimensionScore(
            dimension=dim.get("dimension", "unknown"),
            score_a=float(dim.get("score_a", 5)),
            score_b=float(dim.get("score_b", 5)),
            justification=dim.get("justification", ""),
        ))

    # Parse winner - adjust for order
    winner_str = data.get("overall_winner", "TIE").upper()

    if winner_str == "A":
        # "A" in judge's view corresponds to first_output
        winner = Verdict.A_WINS if order == "ab" else Verdict.B_WINS
    elif winner_str == "B":
        winner = Verdict.B_WINS if order == "ab" else Verdict.A_WINS
    else:
        winner = Verdict.TIE

    return JudgeVerdict(
        winner=winner,
        dimension_scores=tuple(dimension_scores),
        confidence=float(data.get("confidence", 0.5)),
        order=order,
        raw_response=response,
    )


def aggregate_verdicts(
    verdicts: list[JudgeVerdict],
) -> AggregatedVerdict:
    """Aggregate multiple judge verdicts via majority vote."""
    if not verdicts:
        return AggregatedVerdict(
            winner=Verdict.TIE,
            individual_verdicts=(),
            agreement_rate=0.0,
            avg_score_a=0.0,
            avg_score_b=0.0,
            position_bias=0.0,
        )

    # Count votes
    a_wins = sum(1 for v in verdicts if v.winner == Verdict.A_WINS)
    b_wins = sum(1 for v in verdicts if v.winner == Verdict.B_WINS)
    ties = sum(1 for v in verdicts if v.winner == Verdict.TIE)

    # Majority vote
    if a_wins > b_wins and a_wins > ties:
        winner = Verdict.A_WINS
    elif b_wins > a_wins and b_wins > ties:
        winner = Verdict.B_WINS
    else:
        winner = Verdict.TIE

    # Calculate agreement rate
    max_votes = max(a_wins, b_wins, ties)
    agreement_rate = max_votes / len(verdicts)

    # Calculate average scores
    all_scores_a: list[float] = []
    all_scores_b: list[float] = []
    for v in verdicts:
        for ds in v.dimension_scores:
            all_scores_a.append(ds.score_a)
            all_scores_b.append(ds.score_b)

    avg_score_a = sum(all_scores_a) / len(all_scores_a) if all_scores_a else 5.0
    avg_score_b = sum(all_scores_b) / len(all_scores_b) if all_scores_b else 5.0

    # Calculate position bias
    ab_wins = sum(
        1 for v in verdicts
        if v.order == "ab" and v.winner == Verdict.A_WINS
    )
    ba_wins = sum(
        1 for v in verdicts
        if v.order == "ba" and v.winner == Verdict.A_WINS
    )
    ab_total = sum(1 for v in verdicts if v.order == "ab")
    ba_total = sum(1 for v in verdicts if v.order == "ba")

    ab_rate = ab_wins / ab_total if ab_total > 0 else 0.5
    ba_rate = ba_wins / ba_total if ba_total > 0 else 0.5
    position_bias = abs(ab_rate - ba_rate)

    return AggregatedVerdict(
        winner=winner,
        individual_verdicts=tuple(verdicts),
        agreement_rate=agreement_rate,
        avg_score_a=avg_score_a,
        avg_score_b=avg_score_b,
        position_bias=position_bias,
    )
