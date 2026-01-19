"""Naaru Benchmark Types (RFC-027).

Data structures for the Naaru benchmark suite:
- 7 conditions (A-G) for ablation testing
- Naaru-specific metrics (consensus, refinement, escalation)
- Statistical analysis results
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class NaaruCondition(str, Enum):
    """11 conditions (A-K) for Naaru ablation testing.

    These systematically enable features to isolate each technique's contribution:
    - BASELINE: Raw model capability
    - BASELINE_LENS: Lens context alone
    - HARMONIC: Multi-persona voting (no lens)
    - HARMONIC_LENS: Harmonic + lens personas
    - RESONANCE: Feedback loop refinement
    - NAARU_FULL: All techniques combined
    - NAARU_FULL_LENS: Full Naaru + lens context
    - ROTATION: Single generation with frame markers (RFC-028)
    - ROTATION_LENS: Rotation + lens context
    - HARMONIC_DIVERGENT: Harmonic with divergent personas + temp spread
    - ROTATION_DIVERGENT: Rotation with divergent frame emphasis

    Key comparisons:
    - E vs F: Tiered validation cost savings
    - C vs A: Harmonic Synthesis quality gain
    - D vs C: Lens persona boost
    - G vs A: Full Naaru + lens improvement
    - H vs C: Rotation vs Harmonic (cost vs quality)
    - J vs C: Divergent personas impact
    """

    # A: Raw model, no system prompt
    BASELINE = "baseline"

    # B: Add lens context
    BASELINE_LENS = "baseline_lens"

    # C: Multi-persona voting (hardcoded personas)
    HARMONIC = "harmonic"

    # D: Multi-persona from lens file
    HARMONIC_LENS = "harmonic_lens"

    # E: Feedback loop (full judge)
    RESONANCE = "resonance"

    # F: Full Naaru with tiered validation
    NAARU_FULL = "naaru_full"

    # G: Full Naaru + lens context
    NAARU_FULL_LENS = "naaru_full_lens"

    # H: Single generation with thought rotation frames (RFC-028)
    ROTATION = "rotation"

    # I: Rotation + lens context
    ROTATION_LENS = "rotation_lens"

    # J: Harmonic with divergent personas + temperature spread
    HARMONIC_DIVERGENT = "harmonic_divergent"

    # K: Rotation with divergent frame emphasis
    ROTATION_DIVERGENT = "rotation_divergent"


@dataclass(slots=True)
class HarmonicMetrics:
    """Metrics from Harmonic Synthesis (multi-persona voting).

    Attributes:
        consensus_strength: Agreement among persona voters (max_votes / total_votes)
        persona_outputs: Raw outputs from each persona
        persona_names: Names of personas used
        winning_persona: Which persona's output won
        vote_distribution: How votes were distributed
        temperature_strategy: Which temperature strategy was used
        persona_temperatures: Temperature used for each persona
    """

    consensus_strength: float  # 0.0-1.0, target > 0.66
    persona_outputs: tuple[str, ...]
    persona_names: tuple[str, ...]
    winning_persona: str
    vote_distribution: dict[str, int] = field(default_factory=dict)
    temperature_strategy: str = "uniform_med"
    persona_temperatures: tuple[float, ...] = ()

    @property
    def persona_diversity(self) -> float:
        """Calculate output diversity (avg pairwise edit distance / length)."""
        if len(self.persona_outputs) < 2:
            return 0.0

        total_distance = 0
        total_length = 0
        count = 0

        for i, out1 in enumerate(self.persona_outputs):
            for out2 in self.persona_outputs[i+1:]:
                # Simple character-level distance
                total_distance += sum(
                    1 for a, b in zip(out1, out2, strict=False) if a != b
                )
                total_distance += abs(len(out1) - len(out2))
                total_length += max(len(out1), len(out2))
                count += 1

        if total_length == 0 or count == 0:
            return 0.0

        return total_distance / total_length


@dataclass(slots=True)
class ResonanceMetrics:
    """Metrics from Resonance feedback loop.

    Attributes:
        refinement_attempts: Number of refinement iterations
        initial_score: Quality score before refinement
        final_score: Quality score after refinement
        issues_addressed: Issues that were fixed
        escalated_to_full_judge: Whether FunctionGemma escalated to full judge
    """

    refinement_attempts: int  # 0-N, where N is max_attempts
    initial_score: float
    final_score: float
    issues_addressed: tuple[str, ...] = ()
    escalated_to_full_judge: bool = False

    @property
    def refinement_gain(self) -> float:
        """Quality improvement from feedback loop.

        Formula: (final_score - initial_score) / initial_score
        Target: > 0.1 (10% improvement)
        """
        if self.initial_score == 0:
            return 0.0
        return (self.final_score - self.initial_score) / self.initial_score

    @property
    def was_refined(self) -> bool:
        """Whether refinement actually occurred."""
        return self.refinement_attempts > 0


@dataclass(slots=True)
class RotationMetrics:
    """Metrics from Thought Rotation (RFC-028).

    Attributes:
        frames_used: Which cognitive frames were used
        frame_token_counts: Approximate tokens per frame
        divergent_mode: Whether divergent frames (adversary/advocate/naive) were used
    """

    frames_used: tuple[str, ...]
    frame_token_counts: dict[str, int] = field(default_factory=dict)
    divergent_mode: bool = False

    @property
    def n_frames(self) -> int:
        """Number of distinct frames used."""
        return len(self.frames_used)

    @property
    def frame_coverage(self) -> float:
        """Fraction of available frames that were used."""
        total_frames = 6 if self.divergent_mode else 5
        return self.n_frames / total_frames

    @property
    def total_frame_tokens(self) -> int:
        """Total tokens across all frames."""
        return sum(self.frame_token_counts.values())


@dataclass(slots=True)
class NaaruConditionOutput:
    """Output from a single Naaru condition run.

    Extends the base ConditionOutput with Naaru-specific metrics.
    """

    condition: NaaruCondition
    output: str
    tokens_used: int
    time_seconds: float

    # Naaru-specific metrics (optional based on condition)
    harmonic_metrics: HarmonicMetrics | None = None
    resonance_metrics: ResonanceMetrics | None = None
    rotation_metrics: RotationMetrics | None = None

    # System prompt used (for debugging)
    system_prompt: str = ""

    @property
    def quality_per_token(self) -> float:
        """Quality normalized by token usage (needs external score)."""
        return 0.0  # Computed externally with judge scores

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "condition": self.condition.value,
            "output": self.output,
            "tokens_used": self.tokens_used,
            "time_seconds": self.time_seconds,
        }

        if self.harmonic_metrics:
            result["harmonic"] = {
                "consensus_strength": self.harmonic_metrics.consensus_strength,
                "persona_names": list(self.harmonic_metrics.persona_names),
                "winning_persona": self.harmonic_metrics.winning_persona,
                "persona_diversity": self.harmonic_metrics.persona_diversity,
                "temperature_strategy": self.harmonic_metrics.temperature_strategy,
                "persona_temperatures": list(self.harmonic_metrics.persona_temperatures),
            }

        if self.resonance_metrics:
            result["resonance"] = {
                "refinement_attempts": self.resonance_metrics.refinement_attempts,
                "initial_score": self.resonance_metrics.initial_score,
                "final_score": self.resonance_metrics.final_score,
                "refinement_gain": self.resonance_metrics.refinement_gain,
                "escalated": self.resonance_metrics.escalated_to_full_judge,
            }

        if self.rotation_metrics:
            result["rotation"] = {
                "frames_used": list(self.rotation_metrics.frames_used),
                "frame_token_counts": self.rotation_metrics.frame_token_counts,
                "n_frames": self.rotation_metrics.n_frames,
                "frame_coverage": self.rotation_metrics.frame_coverage,
                "divergent_mode": self.rotation_metrics.divergent_mode,
            }

        return result


@dataclass(slots=True)
class NaaruTaskResult:
    """Result from running a single task across Naaru conditions."""

    task_id: str
    outputs: dict[NaaruCondition, NaaruConditionOutput]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def get_output(self, condition: NaaruCondition) -> NaaruConditionOutput | None:
        """Get output for a specific condition."""
        return self.outputs.get(condition)

    @property
    def conditions_run(self) -> list[NaaruCondition]:
        """List of conditions that were run."""
        return list(self.outputs.keys())

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "outputs": {
                cond.value: out.to_dict()
                for cond, out in self.outputs.items()
            },
        }


@dataclass(slots=True)
class ConditionStats:
    """Aggregate statistics for a single condition across all tasks."""

    condition: NaaruCondition
    n_tasks: int

    # Score statistics
    mean_score: float
    std_score: float
    min_score: float
    max_score: float

    # Token statistics
    mean_tokens: float
    total_tokens: int

    # Time statistics
    mean_time_seconds: float
    total_time_seconds: float

    # Condition-specific
    mean_consensus_strength: float | None = None  # For HARMONIC*
    mean_refinement_attempts: float | None = None  # For RESONANCE*
    mean_refinement_gain: float | None = None  # For RESONANCE*
    escalation_rate: float | None = None  # For NAARU_FULL*

    @property
    def quality_per_token(self) -> float:
        """Quality score per 1000 tokens."""
        if self.mean_tokens == 0:
            return 0.0
        return self.mean_score / self.mean_tokens * 1000


@dataclass(slots=True)
class PairwiseComparison:
    """Statistical comparison between two conditions."""

    condition_a: NaaruCondition
    condition_b: NaaruCondition

    # Scores
    mean_a: float
    mean_b: float

    # Effect size
    cohens_d: float
    effect_interpretation: str  # "negligible", "small", "medium", "large"

    # Significance
    statistic: float
    p_value: float
    significant: bool  # After Bonferroni correction

    # Win/loss/tie
    wins_a: int
    wins_b: int
    ties: int

    @property
    def mean_difference(self) -> float:
        """Mean score difference (A - B)."""
        return self.mean_a - self.mean_b

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "condition_a": self.condition_a.value,
            "condition_b": self.condition_b.value,
            "mean_a": self.mean_a,
            "mean_b": self.mean_b,
            "cohens_d": self.cohens_d,
            "effect_interpretation": self.effect_interpretation,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.significant,
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
        }


@dataclass(slots=True)
class NaaruAnalysis:
    """Complete statistical analysis of Naaru benchmark results."""

    # Per-condition statistics
    condition_stats: dict[NaaruCondition, ConditionStats]

    # Pairwise comparisons
    comparisons: list[PairwiseComparison]

    # Hypothesis test results
    hypothesis_results: dict[str, dict]  # H1, H2, ... → results

    # Interaction effect (Naaru × Lens)
    interaction_effect: float  # > 0 = synergistic, ≈ 0 = additive, < 0 = diminishing
    interaction_interpretation: str

    # Pareto frontier (quality vs cost)
    pareto_frontier: list[NaaruCondition]  # Conditions on the frontier

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "condition_stats": {
                cond.value: {
                    "mean_score": stats.mean_score,
                    "std_score": stats.std_score,
                    "mean_tokens": stats.mean_tokens,
                    "quality_per_token": stats.quality_per_token,
                }
                for cond, stats in self.condition_stats.items()
            },
            "comparisons": [c.to_dict() for c in self.comparisons],
            "hypothesis_results": self.hypothesis_results,
            "interaction_effect": self.interaction_effect,
            "interaction_interpretation": self.interaction_interpretation,
            "pareto_frontier": [c.value for c in self.pareto_frontier],
        }


@dataclass(slots=True)
class NaaruBenchmarkResults:
    """Complete results from a Naaru benchmark run."""

    timestamp: str
    model: str
    judge_model: str
    conditions: list[NaaruCondition]
    results: list[NaaruTaskResult]

    # Optional analysis (computed post-run)
    analysis: NaaruAnalysis | None = None

    # Metadata
    version: str = "0.1.0"
    config: dict = field(default_factory=dict)

    @property
    def n_tasks(self) -> int:
        """Number of tasks run."""
        return len(self.results)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "judge_model": self.judge_model,
            "version": self.version,
            "n_tasks": self.n_tasks,
            "conditions": [c.value for c in self.conditions],
            "config": self.config,
            "results": [r.to_dict() for r in self.results],
            "analysis": self.analysis.to_dict() if self.analysis else None,
        }
