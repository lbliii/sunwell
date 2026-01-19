"""Benchmark data types (RFC-018).

Core data structures for the quality benchmark framework:
- Task definitions loaded from YAML
- Results from benchmark runs
- Evaluation outcomes from all three tiers
- Statistical summaries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal


class Condition(str, Enum):
    """Benchmark execution conditions."""

    BARE = "bare"           # No system prompt
    FLAT = "flat"           # Full lens context injected
    SELECTIVE = "selective" # Sunwell selective retrieval
    ROUTED = "routed"       # CognitiveRouter + selective retrieval
    SELF_DIRECTED = "self_directed"  # RFC-027: Model calls expertise tools during generation
    PREFETCH = "prefetch"   # RFC-031: Tool Orchestrator Shard pre-fetches expertise
    COMPETITOR = "competitor"  # Optional competitor baseline


class PromptStrategy(str, Enum):
    """How to present heuristics in the system prompt.

    Different strategies work better for different model sizes:
    - Small models (1-2B): constraints, raw
    - Medium models (3-8B): guided, cot
    - Large models (8B+): cot, few_shot, react
    """

    RAW = "raw"               # Dump heuristics as-is
    GUIDED = "guided"         # "Apply these principles to your response"
    COT = "cot"               # Chain-of-thought: THINK → PLAN → CODE → VERIFY
    CONSTRAINTS = "constraints"  # Extract MUST/MUST NOT from heuristics
    FEW_SHOT = "few_shot"     # Include example of applying heuristics


class NaaruMode(str, Enum):
    """Naaru coordination components to enable.

    These add quality at the cost of more tokens/latency:
    - harmonic: 3x tokens (3 personas)
    - resonance: 1.5x tokens (feedback loop)
    - full: 4x tokens (both)
    """

    NONE = "none"             # Single generation
    HARMONIC = "harmonic"     # Multi-persona voting (Self-Consistency)
    RESONANCE = "resonance"   # Feedback loop refinement
    FULL = "full"             # Harmonic + Resonance


class TaskCategory(str, Enum):
    """Benchmark task categories."""

    DOCUMENTATION = "documentation"
    CODE_REVIEW = "code_review"
    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"


class Verdict(str, Enum):
    """Judge verdict for pairwise comparison."""

    A_WINS = "a"
    B_WINS = "b"
    TIE = "tie"


# =============================================================================
# Task Definitions
# =============================================================================


@dataclass(frozen=True, slots=True)
class RubricDimension:
    """A single evaluation dimension in the rubric."""

    dimension: str      # e.g., "accuracy", "completeness"
    weight: float       # 0.0-1.0, weights should sum to 1.0
    criteria: str       # Human-readable evaluation criteria


@dataclass(frozen=True, slots=True)
class TaskEvaluation:
    """Evaluation configuration for a benchmark task."""

    rubric: tuple[RubricDimension, ...] = ()
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    ground_truth_issues: tuple[str, ...] = ()  # For code review tasks


@dataclass(slots=True)
class BenchmarkTask:
    """A single benchmark task.

    Tasks are loaded from YAML files in benchmark/tasks/.
    """

    id: str                           # Unique task identifier
    category: TaskCategory            # docs, review, code, analysis
    subcategory: str                  # e.g., "api_reference", "security"
    prompt: str                       # The task prompt
    lens: str                         # Path to lens file to use
    evaluation: TaskEvaluation        # Evaluation criteria
    context_files: tuple[str, ...] = ()  # Optional fixture files
    test_suite: str | None = None     # For code generation tasks
    target_persona: str | None = None # For persona adherence testing
    source_path: Path | None = None   # Path to YAML file


# =============================================================================
# Execution Results
# =============================================================================


@dataclass(slots=True)
class ConditionOutput:
    """Output from a single condition execution."""

    condition: Condition
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    system_prompt: str = ""  # The system prompt used


@dataclass(slots=True)
class RetrievalMetrics:
    """Metrics for evaluating retrieval quality (RFC-018 Section: Retrieval Quality Metrics)."""

    precision_at_k: float      # Were retrieved heuristics relevant?
    recall: float              # Did we miss critical heuristics?
    avg_relevance: float       # Human-rated quality of retrieved set
    retrieval_latency_ms: int  # Time to retrieve
    retrieved_ids: tuple[str, ...] = ()  # IDs of retrieved heuristics

    @classmethod
    def empty(cls) -> RetrievalMetrics:
        """Create empty metrics for non-retrieval conditions."""
        return cls(
            precision_at_k=0.0,
            recall=0.0,
            avg_relevance=0.0,
            retrieval_latency_ms=0,
        )


@dataclass(slots=True)
class RoutingMetrics:
    """Metrics for CognitiveRouter performance (RFC-020)."""

    intent: str                 # Classified intent
    lens_selected: str          # Lens chosen by router
    focus_terms: tuple[str, ...]  # Focus terms for retrieval boosting
    complexity: str             # simple/moderate/complex
    confidence: float           # Router's confidence (0-1)
    routing_latency_ms: int     # Time for routing decision
    top_k_adjusted: int         # Final top_k used (may differ from default)
    reasoning: str = ""         # Router's explanation

    @classmethod
    def empty(cls) -> RoutingMetrics:
        """Create empty metrics when routing not used."""
        return cls(
            intent="none",
            lens_selected="",
            focus_terms=(),
            complexity="",
            confidence=0.0,
            routing_latency_ms=0,
            top_k_adjusted=0,
        )


@dataclass(slots=True)
class SelfDirectedMetrics:
    """Metrics for self-directed expertise retrieval (RFC-027).

    Tracks how models use expertise tools during generation:
    - Tool call frequency and patterns
    - Topics queried
    - Whether verification was used
    - ReAct loop iterations
    """

    total_tool_calls: int               # Total expertise tool invocations
    list_expertise_calls: int           # list_expertise_areas() calls
    get_expertise_calls: int            # get_expertise() calls
    verify_calls: int                   # verify_against_expertise() calls
    topics_queried: tuple[str, ...]     # Topics passed to get_expertise
    heuristics_retrieved: int           # Total heuristics returned
    verification_passed: bool | None    # Did verify return "no violations"?
    react_iterations: int               # Number of ReAct loop iterations
    tool_latency_ms: int                # Total time in expertise tools

    @classmethod
    def empty(cls) -> SelfDirectedMetrics:
        """Create empty metrics when self-directed mode not used."""
        return cls(
            total_tool_calls=0,
            list_expertise_calls=0,
            get_expertise_calls=0,
            verify_calls=0,
            topics_queried=(),
            heuristics_retrieved=0,
            verification_passed=None,
            react_iterations=0,
            tool_latency_ms=0,
        )

    @property
    def used_expertise_tools(self) -> bool:
        """True if the model actually called any expertise tools."""
        return self.total_tool_calls > 0

    @property
    def followed_react_pattern(self) -> bool:
        """True if model followed recommended ReAct pattern (list→get→verify)."""
        return (
            self.get_expertise_calls > 0 and
            self.verify_calls > 0
        )


@dataclass(slots=True)
class PrefetchMetrics:
    """Metrics for Tool Orchestrator Shard prefetch (RFC-031).

    Tracks how the Tool Orchestrator Shard pre-fetches expertise
    before generation, allowing small models to benefit from
    expertise without needing tool-calling capability.
    """

    topics_detected: tuple[str, ...]  # Topics found via semantic similarity
    expertise_items: int               # Number of expertise items fetched
    max_relevance_score: float         # Highest relevance score
    min_relevance_score: float         # Lowest relevance score (of fetched items)
    prefetch_latency_ms: int           # Time for prefetch operation
    threshold_used: float              # Similarity threshold
    prompt_expansion_tokens: int       # Tokens added by expertise
    reasoning: str                     # Why these topics were selected

    @classmethod
    def empty(cls) -> PrefetchMetrics:
        """Create empty metrics when prefetch not used."""
        return cls(
            topics_detected=(),
            expertise_items=0,
            max_relevance_score=0.0,
            min_relevance_score=0.0,
            prefetch_latency_ms=0,
            threshold_used=0.0,
            prompt_expansion_tokens=0,
            reasoning="",
        )

    @property
    def found_relevant_expertise(self) -> bool:
        """True if any relevant expertise was found."""
        return self.expertise_items > 0


@dataclass(slots=True)
class TaskResult:
    """Result from running a single task across all conditions."""

    task_id: str
    outputs: dict[str, ConditionOutput]  # Condition name → output
    retrieval_metrics: RetrievalMetrics | None = None
    routing_metrics: RoutingMetrics | None = None  # RFC-020: CognitiveRouter metrics
    self_directed_metrics: SelfDirectedMetrics | None = None  # RFC-027: Self-directed metrics
    prefetch_metrics: PrefetchMetrics | None = None  # RFC-031: Tool Orchestrator Shard
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# Evaluation Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class DeterministicResult:
    """Results from tier-1 deterministic evaluation."""

    must_contain_results: dict[str, bool]      # term → found
    must_not_contain_results: dict[str, bool]  # term → avoided
    tests_pass: bool | None = None             # For code tasks
    lint_clean: bool | None = None
    type_check: bool | None = None

    @property
    def passed(self) -> bool:
        """True if all deterministic checks passed."""
        all_contain = all(self.must_contain_results.values()) if self.must_contain_results else True
        all_avoid = all(self.must_not_contain_results.values()) if self.must_not_contain_results else True
        tests_ok = self.tests_pass if self.tests_pass is not None else True
        return all_contain and all_avoid and tests_ok


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """Score for a single rubric dimension."""

    dimension: str
    score_a: float  # Score for first output (1-10)
    score_b: float  # Score for second output (1-10)
    justification: str


@dataclass(slots=True)
class JudgeVerdict:
    """Result from LLM judge pairwise comparison."""

    winner: Verdict                  # A, B, or TIE
    dimension_scores: tuple[DimensionScore, ...]
    confidence: float               # Judge's self-reported confidence
    order: Literal["ab", "ba"]      # Which output was shown first
    raw_response: str = ""          # Full judge response for debugging


@dataclass(slots=True)
class AggregatedVerdict:
    """Aggregated verdict from multiple judge runs (majority vote)."""

    winner: Verdict
    individual_verdicts: tuple[JudgeVerdict, ...]
    agreement_rate: float           # How often judges agreed
    avg_score_a: float              # Average score for output A
    avg_score_b: float              # Average score for output B
    position_bias: float            # Win rate difference by position


@dataclass(slots=True)
class EvaluationResult:
    """Complete evaluation result for a single task."""

    task_id: str
    deterministic: dict[str, DeterministicResult]  # Condition → results
    judge_results: dict[str, AggregatedVerdict]    # "selective_vs_bare" → verdict
    overall_winner: str = ""  # Which condition won overall

    @property
    def selective_wins(self) -> bool:
        """True if selective retrieval won against all baselines."""
        for key, verdict in self.judge_results.items():
            if "selective" in key:
                # In "selective_vs_X", B is always selective
                if verdict.winner != Verdict.B_WINS:
                    return False
        return True


# =============================================================================
# Aggregate Results
# =============================================================================


@dataclass(slots=True)
class CategoryStats:
    """Statistics for a single task category."""

    category: str
    total_tasks: int
    wins: int
    losses: int
    ties: int
    avg_selective_score: float
    avg_baseline_score: float

    @property
    def win_rate(self) -> float:
        """Win rate (excluding ties)."""
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0


@dataclass(slots=True)
class StatisticalSummary:
    """Statistical analysis of benchmark results (RFC-018 Section: Statistical Rigor)."""

    # Sample info
    n_tasks: int
    n_per_category: dict[str, int]

    # Win/loss/tie counts
    wins: int
    losses: int
    ties: int

    # Effect size
    effect_size_cohens_d: float
    effect_size_interpretation: str  # small/medium/large

    # Significance testing
    p_value: float
    test_statistic: float
    test_name: str  # "Mann-Whitney U" or "Wilcoxon signed-rank"

    # Confidence intervals (bootstrap)
    ci_lower: float
    ci_upper: float
    ci_level: float = 0.95

    # Category breakdowns
    category_stats: tuple[CategoryStats, ...] = ()

    @property
    def significant(self) -> bool:
        """True if results are statistically significant at p < 0.05."""
        return self.p_value < 0.05

    @property
    def win_rate(self) -> float:
        """Overall win rate."""
        total = self.wins + self.losses + self.ties
        return self.wins / total if total > 0 else 0.0

    def claim_level(self) -> str:
        """Determine valid claim level based on RFC-018 criteria.

        Returns:
            - "suggests improvement": p < 0.1, d > 0.2
            - "shows improvement": p < 0.05, d > 0.5
            - "strong evidence": p < 0.01, d > 0.8
            - "insufficient evidence": otherwise
        """
        d = abs(self.effect_size_cohens_d)

        if self.p_value < 0.01 and d > 0.8:
            return "strong evidence"
        elif self.p_value < 0.05 and d > 0.5:
            return "shows improvement"
        elif self.p_value < 0.1 and d > 0.2:
            return "suggests improvement"
        else:
            return "insufficient evidence"


@dataclass(slots=True)
class BenchmarkResults:
    """Complete results from a benchmark run."""

    timestamp: str
    model: str
    task_results: tuple[TaskResult, ...]
    evaluation_results: tuple[EvaluationResult, ...] = ()
    statistics: StatisticalSummary | None = None
    version: str = "0.1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "version": self.version,
            "n_tasks": len(self.task_results),
            "task_ids": [r.task_id for r in self.task_results],
        }
