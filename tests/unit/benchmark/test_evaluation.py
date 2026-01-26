"""Tests for benchmark evaluation package.

Tests for:
- Deterministic evaluation (must_contain, must_not_contain, code checks)
- Judge response parsing
- Vote aggregation
- Position randomization
"""

import pytest

from sunwell.benchmark.evaluation.deterministic import evaluate_deterministic
from sunwell.benchmark.evaluation.judge import (
    aggregate_verdicts,
    parse_judge_response,
)
from sunwell.benchmark.types import (
    BenchmarkTask,
    DeterministicResult,
    JudgeVerdict,
    TaskCategory,
    TaskEvaluation,
    Verdict,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def code_task() -> BenchmarkTask:
    """Code generation task for testing."""
    return BenchmarkTask(
        id="test-code-001",
        category=TaskCategory.CODE_GENERATION,
        subcategory="basic",
        prompt="Write a function",
        lens="test.lens",
        evaluation=TaskEvaluation(
            must_contain=("def", "return"),
            must_not_contain=("eval", "exec"),
        ),
    )


@pytest.fixture
def docs_task() -> BenchmarkTask:
    """Documentation task for testing."""
    return BenchmarkTask(
        id="test-docs-001",
        category=TaskCategory.DOCUMENTATION,
        subcategory="api",
        prompt="Document the API",
        lens="test.lens",
        evaluation=TaskEvaluation(
            must_contain=("## Overview",),
            must_not_contain=("TODO",),
        ),
    )


# =============================================================================
# Deterministic Evaluation Tests
# =============================================================================


class TestMustContainChecks:
    """Tests for must_contain evaluation."""

    def test_all_terms_present_passes(self, code_task: BenchmarkTask):
        """Output with all required terms passes."""
        output = "def add(a, b):\n    return a + b"

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True
        assert result.must_contain_results["return"] is True
        assert result.passed

    def test_missing_term_fails(self, code_task: BenchmarkTask):
        """Output missing required term fails."""
        output = "def add(a, b):\n    a + b"  # No return statement

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True
        assert result.must_contain_results["return"] is False
        assert not result.passed

    def test_case_insensitive_matching(self, code_task: BenchmarkTask):
        """must_contain checks are case-insensitive."""
        output = "DEF add(a, b):\n    RETURN a + b"

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True
        assert result.must_contain_results["return"] is True

    def test_empty_must_contain_passes(self):
        """Empty must_contain always passes."""
        task = BenchmarkTask(
            id="test",
            category=TaskCategory.DOCUMENTATION,
            subcategory="test",
            prompt="Test",
            lens="test.lens",
            evaluation=TaskEvaluation(must_contain=()),
        )

        result = evaluate_deterministic(task, "any content", run_code_tests=False)

        assert result.passed


class TestMustNotContainChecks:
    """Tests for must_not_contain evaluation."""

    def test_forbidden_term_absent_passes(self, code_task: BenchmarkTask):
        """Output without forbidden terms passes."""
        output = "def add(a, b):\n    return a + b"

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_not_contain_results["eval"] is True
        assert result.must_not_contain_results["exec"] is True

    def test_forbidden_term_present_fails(self, code_task: BenchmarkTask):
        """Output with forbidden term fails."""
        output = "def run(code):\n    return eval(code)"

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_not_contain_results["eval"] is False
        assert not result.passed

    def test_case_insensitive_forbidden(self, code_task: BenchmarkTask):
        """must_not_contain checks are case-insensitive."""
        output = "def run(code):\n    return EVAL(code)"

        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_not_contain_results["eval"] is False


class TestCodeBlockExtraction:
    """Tests for code block extraction regex."""

    def test_extracts_python_fenced_blocks(self, code_task: BenchmarkTask):
        """Extracts ```python fenced code blocks."""
        output = """Here's the code:

```python
def add(a, b):
    return a + b
```
"""
        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        # Should find def and return in the code block
        assert result.must_contain_results["def"] is True
        assert result.must_contain_results["return"] is True

    def test_extracts_py_fenced_blocks(self, code_task: BenchmarkTask):
        """Extracts ```py fenced code blocks."""
        output = """```py
def add(a, b):
    return a + b
```"""
        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True

    def test_extracts_python3_fenced_blocks(self, code_task: BenchmarkTask):
        """Extracts ```python3 fenced code blocks."""
        output = """```python3
def add(a, b):
    return a + b
```"""
        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True

    def test_extracts_untagged_blocks(self, code_task: BenchmarkTask):
        """Extracts untagged ``` code blocks."""
        output = """```
def add(a, b):
    return a + b
```"""
        result = evaluate_deterministic(code_task, output, run_code_tests=False)

        assert result.must_contain_results["def"] is True


# =============================================================================
# Judge Response Parsing Tests
# =============================================================================


class TestParseJudgeResponse:
    """Tests for parse_judge_response."""

    def test_parses_clean_json(self):
        """Parses well-formed JSON response."""
        response = """{
            "dimensions": [
                {"dimension": "accuracy", "score_a": 8, "score_b": 7, "justification": "A is better"}
            ],
            "overall_winner": "A",
            "confidence": 0.85
        }"""

        verdict = parse_judge_response(response, order="ab")

        assert verdict.winner == Verdict.A_WINS
        assert verdict.confidence == 0.85
        assert len(verdict.dimension_scores) == 1
        assert verdict.dimension_scores[0].score_a == 8.0

    def test_parses_json_in_markdown(self):
        """Extracts JSON from markdown code block."""
        response = """Here's my evaluation:

```json
{
    "dimensions": [],
    "overall_winner": "B",
    "confidence": 0.9
}
```"""

        verdict = parse_judge_response(response, order="ab")

        assert verdict.winner == Verdict.B_WINS
        assert verdict.confidence == 0.9

    def test_handles_malformed_json(self):
        """Returns TIE with 0 confidence for malformed JSON."""
        response = "This is not valid JSON at all"

        verdict = parse_judge_response(response, order="ab")

        assert verdict.winner == Verdict.TIE
        assert verdict.confidence == 0.0

    def test_adjusts_for_order_ab(self):
        """Winner adjusted correctly for ab order."""
        response = '{"dimensions": [], "overall_winner": "A", "confidence": 0.8}'

        verdict = parse_judge_response(response, order="ab")

        # A in ab order = A wins
        assert verdict.winner == Verdict.A_WINS

    def test_adjusts_for_order_ba(self):
        """Winner adjusted correctly for ba order (swapped)."""
        response = '{"dimensions": [], "overall_winner": "A", "confidence": 0.8}'

        verdict = parse_judge_response(response, order="ba")

        # A in ba order = B wins (because outputs were swapped)
        assert verdict.winner == Verdict.B_WINS

    def test_parses_tie(self):
        """TIE response parsed correctly regardless of order."""
        response = '{"dimensions": [], "overall_winner": "TIE", "confidence": 0.5}'

        verdict_ab = parse_judge_response(response, order="ab")
        verdict_ba = parse_judge_response(response, order="ba")

        assert verdict_ab.winner == Verdict.TIE
        assert verdict_ba.winner == Verdict.TIE

    def test_dimension_scores_parsed(self):
        """Dimension scores extracted correctly."""
        response = """{
            "dimensions": [
                {"dimension": "accuracy", "score_a": 9, "score_b": 7, "justification": "Test"},
                {"dimension": "completeness", "score_a": 8, "score_b": 8, "justification": "Equal"}
            ],
            "overall_winner": "A",
            "confidence": 0.9
        }"""

        verdict = parse_judge_response(response, order="ab")

        assert len(verdict.dimension_scores) == 2
        assert verdict.dimension_scores[0].dimension == "accuracy"
        assert verdict.dimension_scores[0].score_a == 9.0
        assert verdict.dimension_scores[1].dimension == "completeness"

    def test_missing_dimensions_defaults(self):
        """Missing dimension fields use defaults."""
        response = """{
            "dimensions": [
                {"dimension": "test"}
            ],
            "overall_winner": "A",
            "confidence": 0.5
        }"""

        verdict = parse_judge_response(response, order="ab")

        # Missing scores default to 5
        assert verdict.dimension_scores[0].score_a == 5.0
        assert verdict.dimension_scores[0].score_b == 5.0
        assert verdict.dimension_scores[0].justification == ""


# =============================================================================
# Verdict Aggregation Tests
# =============================================================================


class TestAggregateVerdicts:
    """Tests for aggregate_verdicts majority voting."""

    def test_unanimous_a_wins(self):
        """All A votes → A wins."""
        verdicts = [
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.9, order="ab"),
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.8, order="ba"),
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.85, order="ab"),
        ]

        result = aggregate_verdicts(verdicts)

        assert result.winner == Verdict.A_WINS
        assert result.agreement_rate == 1.0

    def test_majority_b_wins(self):
        """2-1 majority for B → B wins."""
        verdicts = [
            JudgeVerdict(winner=Verdict.B_WINS, dimension_scores=(), confidence=0.9, order="ab"),
            JudgeVerdict(winner=Verdict.B_WINS, dimension_scores=(), confidence=0.8, order="ba"),
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.7, order="ab"),
        ]

        result = aggregate_verdicts(verdicts)

        assert result.winner == Verdict.B_WINS
        assert result.agreement_rate == pytest.approx(2 / 3)

    def test_tie_when_split(self):
        """1-1-1 split → TIE."""
        verdicts = [
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.9, order="ab"),
            JudgeVerdict(winner=Verdict.B_WINS, dimension_scores=(), confidence=0.8, order="ba"),
            JudgeVerdict(winner=Verdict.TIE, dimension_scores=(), confidence=0.7, order="ab"),
        ]

        result = aggregate_verdicts(verdicts)

        assert result.winner == Verdict.TIE
        assert result.agreement_rate == pytest.approx(1 / 3)

    def test_empty_verdicts_returns_tie(self):
        """Empty list → TIE with 0 agreement."""
        result = aggregate_verdicts([])

        assert result.winner == Verdict.TIE
        assert result.agreement_rate == 0.0
        assert result.avg_score_a == 0.0
        assert result.avg_score_b == 0.0

    def test_position_bias_calculated(self):
        """Position bias measures win rate difference by position."""
        verdicts = [
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.9, order="ab"),
            JudgeVerdict(winner=Verdict.A_WINS, dimension_scores=(), confidence=0.8, order="ab"),
            JudgeVerdict(winner=Verdict.B_WINS, dimension_scores=(), confidence=0.7, order="ba"),
        ]

        result = aggregate_verdicts(verdicts)

        # 2 ab order: 2 A wins → 100% A win rate
        # 1 ba order: 0 A wins → 0% A win rate
        # Bias = |1.0 - 0.0| = 1.0
        assert result.position_bias == pytest.approx(1.0)

    def test_average_scores_calculated(self):
        """Average scores computed from dimension scores."""
        verdicts = [
            JudgeVerdict(
                winner=Verdict.A_WINS,
                dimension_scores=(
                    _make_dimension_score("d1", 8.0, 6.0),
                    _make_dimension_score("d2", 9.0, 7.0),
                ),
                confidence=0.9,
                order="ab",
            ),
        ]

        result = aggregate_verdicts(verdicts)

        assert result.avg_score_a == pytest.approx(8.5)
        assert result.avg_score_b == pytest.approx(6.5)


# =============================================================================
# Helpers
# =============================================================================


def _make_dimension_score(dimension: str, score_a: float, score_b: float):
    """Helper to create DimensionScore."""
    from sunwell.benchmark.types import DimensionScore

    return DimensionScore(
        dimension=dimension,
        score_a=score_a,
        score_b=score_b,
        justification="Test",
    )
