"""Benchmark Evaluator (RFC-018).

Three-tier evaluation system:
1. Deterministic checks (must_contain, must_not_contain, code tests)
2. LLM-as-Judge pairwise comparison with position randomization
3. Human evaluation protocol (not automated)
"""


import json
import random
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.benchmark.types import (
    AggregatedVerdict,
    BenchmarkTask,
    DeterministicResult,
    DimensionScore,
    EvaluationResult,
    JudgeVerdict,
    TaskResult,
    Verdict,
)
from sunwell.models.protocol import GenerateOptions, ModelProtocol

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


# =============================================================================
# Evaluator
# =============================================================================


@dataclass
class BenchmarkEvaluator:
    """Evaluate benchmark outputs using three-tier methodology.

    Usage:
        evaluator = BenchmarkEvaluator(judge_model=judge)
        result = await evaluator.evaluate(task, task_result)
    """

    judge_model: ModelProtocol
    num_judge_runs: int = 3  # For majority vote
    run_code_tests: bool = True  # Enable code execution checks

    async def evaluate(
        self,
        task: BenchmarkTask,
        result: TaskResult,
    ) -> EvaluationResult:
        """Run all evaluation tiers for a single task.

        Args:
            task: The benchmark task definition
            result: The outputs from running the task

        Returns:
            EvaluationResult with deterministic and judge evaluations
        """
        # Tier 1: Deterministic checks for each condition
        deterministic: dict[str, DeterministicResult] = {}
        for condition_name, output in result.outputs.items():
            deterministic[condition_name] = self._deterministic_eval(
                task=task,
                output=output.content,
            )

        # Tier 2: LLM Judge pairwise comparisons
        judge_results: dict[str, AggregatedVerdict] = {}

        # Compare selective vs each baseline
        if "selective" in result.outputs:
            selective_output = result.outputs["selective"].content

            for baseline in ["bare", "flat"]:
                if baseline in result.outputs:
                    baseline_output = result.outputs[baseline].content

                    verdict = await self._llm_judge(
                        task=task,
                        output_a=baseline_output,
                        output_b=selective_output,
                    )
                    judge_results[f"selective_vs_{baseline}"] = verdict

        # Determine overall winner
        overall_winner = self._determine_winner(judge_results)

        return EvaluationResult(
            task_id=task.id,
            deterministic=deterministic,
            judge_results=judge_results,
            overall_winner=overall_winner,
        )

    def _deterministic_eval(
        self,
        task: BenchmarkTask,
        output: str,
    ) -> DeterministicResult:
        """Tier 1: Fast, reproducible checks."""
        output_lower = output.lower()

        # Must-contain checks
        must_contain_results: dict[str, bool] = {}
        for term in task.evaluation.must_contain:
            must_contain_results[term] = term.lower() in output_lower

        # Must-not-contain checks
        must_not_contain_results: dict[str, bool] = {}
        for term in task.evaluation.must_not_contain:
            must_not_contain_results[term] = term.lower() not in output_lower

        # Code execution checks (for code_generation tasks)
        tests_pass = None
        lint_clean = None
        type_check = None

        if task.category.value == "code_generation" and self.run_code_tests:
            tests_pass, lint_clean, type_check = self._run_code_checks(
                output=output,
                test_suite=task.test_suite,
            )

        return DeterministicResult(
            must_contain_results=must_contain_results,
            must_not_contain_results=must_not_contain_results,
            tests_pass=tests_pass,
            lint_clean=lint_clean,
            type_check=type_check,
        )

    def _run_code_checks(
        self,
        output: str,
        test_suite: str | None,
    ) -> tuple[bool | None, bool | None, bool | None]:
        """Run code quality checks on generated code.

        Returns:
            Tuple of (tests_pass, lint_clean, type_check)
        """
        # Extract code blocks from output
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', output, re.DOTALL)

        if not code_blocks:
            return None, None, None

        code = "\n\n".join(code_blocks)

        tests_pass = None
        lint_clean = None
        type_check = None

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
        ) as f:
            f.write(code)
            temp_path = Path(f.name)

        try:
            # Lint check with ruff
            try:
                result = subprocess.run(
                    ["ruff", "check", str(temp_path), "--quiet"],
                    capture_output=True,
                    timeout=30,
                )
                lint_clean = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                lint_clean = None

            # Type check with mypy
            try:
                result = subprocess.run(
                    ["mypy", str(temp_path), "--ignore-missing-imports"],
                    capture_output=True,
                    timeout=60,
                )
                type_check = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                type_check = None

            # Run tests if test suite provided
            if test_suite:
                try:
                    result = subprocess.run(
                        ["python", "-m", "pytest", test_suite, "-v"],
                        capture_output=True,
                        timeout=120,
                    )
                    tests_pass = result.returncode == 0
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    tests_pass = None
        finally:
            temp_path.unlink(missing_ok=True)

        return tests_pass, lint_clean, type_check

    async def _llm_judge(
        self,
        task: BenchmarkTask,
        output_a: str,
        output_b: str,
    ) -> AggregatedVerdict:
        """Tier 2: Pairwise LLM evaluation with position randomization.

        Runs multiple comparisons with randomized order and aggregates
        via majority vote to reduce position bias.
        """
        verdicts: list[JudgeVerdict] = []

        for _ in range(self.num_judge_runs):
            # Randomize order to prevent position bias
            if random.random() > 0.5:
                first, second = output_a, output_b
                order = "ab"
            else:
                first, second = output_b, output_a
                order = "ba"

            verdict = await self._single_judge_call(
                task=task,
                first_output=first,
                second_output=second,
                order=order,
            )
            verdicts.append(verdict)

        return self._aggregate_verdicts(verdicts)

    async def _single_judge_call(
        self,
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
        result = await self.judge_model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.1,  # Low temperature for consistency
                max_tokens=1000,
            ),
        )

        # Parse response
        return self._parse_judge_response(result.text, order)

    def _parse_judge_response(self, response: str, order: str) -> JudgeVerdict:
        """Parse the judge's JSON response."""
        # Try to extract JSON from response
        try:
            # Handle potential markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)

            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: try to find JSON-like structure
            try:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(response[json_start:json_end])
                else:
                    raise ValueError("No JSON found")
            except (json.JSONDecodeError, ValueError):
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

    def _aggregate_verdicts(
        self,
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

    def _determine_winner(
        self,
        judge_results: dict[str, AggregatedVerdict],
    ) -> str:
        """Determine overall winner across all comparisons.

        Returns "selective" if it wins all comparisons, baseline name otherwise.
        """
        if not judge_results:
            return ""

        # Check if selective wins all comparisons
        selective_wins_all = all(
            v.winner == Verdict.B_WINS  # B is always selective in our comparisons
            for v in judge_results.values()
        )

        if selective_wins_all:
            return "selective"

        # Find the baseline that selective lost to
        for key, verdict in judge_results.items():
            if verdict.winner == Verdict.A_WINS:
                # Extract baseline name from key like "selective_vs_bare"
                return key.replace("selective_vs_", "")

        return "tie"

    async def evaluate_suite(
        self,
        tasks: list[BenchmarkTask],
        results: list[TaskResult],
    ) -> list[EvaluationResult]:
        """Evaluate all results from a benchmark suite."""
        # Create task lookup
        task_map = {t.id: t for t in tasks}

        evaluations: list[EvaluationResult] = []

        for result in results:
            task = task_map.get(result.task_id)
            if task is None:
                continue

            print(f"  Evaluating {result.task_id}...", end=" ", flush=True)
            try:
                evaluation = await self.evaluate(task, result)
                evaluations.append(evaluation)
                winner = "✓ selective" if evaluation.selective_wins else f"✗ {evaluation.overall_winner}"
                print(winner)
            except Exception as e:
                print(f"✗ {e}")

        return evaluations
