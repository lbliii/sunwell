"""Evaluation Framework Types (RFC-098).

Canonical type definitions for evaluation tasks, results, and comparisons.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# =============================================================================
# TASK DEFINITION
# =============================================================================


@dataclass(frozen=True, slots=True)
class FullStackTask:
    """A complex multi-file evaluation task.

    Defines what both single-shot and Sunwell will be asked to build,
    along with expected outputs and evaluation criteria.

    Attributes:
        name: Unique task identifier (e.g., "forum_app").
        prompt: The task prompt given to both executors.
        description: Human-readable description for UI.
        available_tools: Tools both sides get access to.
        expected_structure: File tree expectations (path -> "required"|"optional").
        expected_features: Quality features to check for.
        reference_path: Optional path to reference implementation.
        estimated_minutes: Estimated runtime for progress UI.
    """

    name: str
    prompt: str
    description: str
    available_tools: frozenset[str]
    expected_structure: dict[str, Any]
    expected_features: frozenset[str]
    reference_path: str | None = None
    estimated_minutes: int = 10


# =============================================================================
# EXECUTION RESULTS
# =============================================================================


@dataclass(frozen=True, slots=True)
class SingleShotResult:
    """Result from single-shot execution.

    Attributes:
        files: List of file paths created.
        output_dir: Directory where files were written.
        time_seconds: Execution time.
        turns: Always 1 for single-shot.
        input_tokens: Input tokens used.
        output_tokens: Output tokens generated.
    """

    files: tuple[str, ...]
    output_dir: Path
    time_seconds: float
    turns: int = 1
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class SunwellResult:
    """Result from Sunwell full-stack execution.

    Attributes:
        files: List of file paths created.
        output_dir: Directory where files were written.
        time_seconds: Execution time.
        turns: Number of generation/refinement turns.
        input_tokens: Total input tokens across all turns.
        output_tokens: Total output tokens across all turns.
        lens_used: Which lens was applied.
        judge_scores: Sequence of judge scores per turn.
        resonance_iterations: Number of refinement iterations.
    """

    files: tuple[str, ...]
    output_dir: Path
    time_seconds: float
    turns: int
    input_tokens: int = 0
    output_tokens: int = 0
    lens_used: str | None = None
    judge_scores: tuple[float, ...] = ()
    resonance_iterations: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def final_judge_score(self) -> float | None:
        """Last judge score, or None if no scoring."""
        return self.judge_scores[-1] if self.judge_scores else None


# =============================================================================
# EVALUATION SCORES
# =============================================================================


@dataclass(frozen=True, slots=True)
class FullStackScore:
    """Evaluation score for a generated project.

    Attributes:
        final_score: Weighted composite score (0-10).
        subscores: Individual dimension scores.
        runnable: Whether the project actually runs.
        files_count: Number of Python files.
        lines_count: Total lines of Python code.
        tests_count: Number of test files/functions.
        error_details: Details if project doesn't run.
    """

    final_score: float
    subscores: dict[str, float]
    runnable: bool
    files_count: int
    lines_count: int
    tests_count: int = 0
    error_details: str | None = None


# =============================================================================
# COMPARISON AND RUN RECORDS
# =============================================================================


@dataclass(frozen=True, slots=True)
class EvaluationDetails:
    """Detailed breakdown of what made the difference.

    Attributes:
        lens_contribution: What the lens added.
        judge_rejections: Issues found by judge.
        resonance_fixes: What resonance fixed.
        features_delta: Features Sunwell has that single-shot lacks.
    """

    lens_contribution: tuple[str, ...] = ()
    judge_rejections: tuple[str, ...] = ()
    resonance_fixes: tuple[str, ...] = ()
    features_delta: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """A single evaluation run with full provenance.

    Stored in SQLite for historical tracking and regression detection.

    Attributes:
        id: Unique identifier (UUID).
        timestamp: When the evaluation was run.
        task: Task name.
        model: Model identifier.
        lens: Lens used (if any).
        sunwell_version: Sunwell version for reproducibility.
        single_shot_score: Baseline score.
        sunwell_score: Sunwell score.
        improvement_percent: Percentage improvement.
        winner: Who won the comparison.
        single_shot_result: Full single-shot result.
        sunwell_result: Full Sunwell result.
        evaluation_details: What made the difference.
        input_tokens: Total input tokens.
        output_tokens: Total output tokens.
        estimated_cost_usd: Estimated API cost.
        git_commit: Git commit hash for provenance.
        config_hash: Hash of full config for reproducibility.
        prompts_snapshot: Full prompts used (for replay).
    """

    id: str
    timestamp: datetime
    task: str
    model: str
    lens: str | None
    sunwell_version: str
    single_shot_score: float
    sunwell_score: float
    improvement_percent: float
    winner: Literal["sunwell", "single_shot", "tie"]
    single_shot_result: SingleShotResult
    sunwell_result: SunwellResult
    evaluation_details: EvaluationDetails
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    git_commit: str | None = None
    config_hash: str = ""
    prompts_snapshot: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationStats:
    """Aggregate statistics from evaluation history.

    Attributes:
        total_runs: Total evaluation runs.
        sunwell_wins: Times Sunwell won.
        single_shot_wins: Times single-shot won.
        ties: Number of ties.
        avg_improvement: Average improvement percentage.
        avg_sunwell_score: Average Sunwell score.
        avg_single_shot_score: Average single-shot score.
        by_task: Stats broken down by task.
        by_model: Stats broken down by model.
        by_lens: Stats broken down by lens.
    """

    total_runs: int
    sunwell_wins: int
    single_shot_wins: int
    ties: int
    avg_improvement: float
    avg_sunwell_score: float
    avg_single_shot_score: float
    by_task: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_lens: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        """Sunwell win rate as percentage."""
        if self.total_runs == 0:
            return 0.0
        return (self.sunwell_wins / self.total_runs) * 100
