"""Consensus Classification — N models vote, supermajority wins.

The hypothesis: For high-stakes decisions, require agreement from multiple
tiny models. Like Byzantine fault tolerance but for AI.

When models agree, we're confident. When they disagree, we escalate or
fall back to a safe default.

Example:
    >>> from sunwell.naaru.experiments import consensus_classify
    >>>
    >>> result = await consensus_classify(
    ...     goal="Build a REST API with auth",
    ...     model=OllamaModel("gemma3:1b"),
    ...     n_voters=7,
    ...     threshold=0.6,
    ... )
    >>> print(f"Consensus: {result.classification} ({result.confidence:.0%})")
    >>> print(f"Votes: {result.vote_distribution}")
"""


import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

T = TypeVar("T")


@dataclass
class ConsensusResult[T]:
    """Result from consensus voting."""

    classification: T
    """The winning classification."""

    confidence: float
    """Agreement ratio (0.0 - 1.0)."""

    vote_distribution: dict[T, int]
    """How many votes each option received."""

    total_voters: int
    """Total number of voters."""

    valid_votes: int
    """Number of voters that returned valid results."""

    consensus_reached: bool
    """Whether threshold was met."""

    @property
    def agreement_ratio(self) -> float:
        """Alias for confidence."""
        return self.confidence

    @property
    def is_unanimous(self) -> bool:
        """All voters agreed."""
        return self.confidence == 1.0

    @property
    def is_split(self) -> bool:
        """No clear winner (confidence < 0.5)."""
        return self.confidence < 0.5


async def consensus_classify(
    goal: str,
    model: ModelProtocol,
    n_voters: int = 7,
    threshold: float = 0.6,
    context: dict[str, Any] | None = None,
    parallel: bool = False,
) -> ConsensusResult:
    """Have N tiny models vote on complexity classification.

    Runs N classification calls sequentially by default (local Ollama friendly).
    Set parallel=True if your Ollama has OLLAMA_NUM_PARALLEL > 1.

    Args:
        goal: The goal to classify
        model: The model to use (same model, N calls)
        n_voters: Number of voters (odd numbers work best)
        threshold: Required agreement ratio (default 0.6 = 60%)
        context: Optional context
        parallel: Run calls in parallel (requires Ollama parallel support)

    Returns:
        ConsensusResult with classification and vote distribution
    """
    from sunwell.routing import UnifiedRouter
    from sunwell.routing.unified import Complexity

    router = UnifiedRouter(model=model)

    # Sequential by default (local Ollama friendly)
    if parallel:
        results = await asyncio.gather(*[
            router.route(goal, context) for _ in range(n_voters)
        ], return_exceptions=True)
    else:
        results = []
        for _i in range(n_voters):
            try:
                r = await router.route(goal, context)
                results.append(r)
            except Exception as e:
                results.append(e)

    # Separate valid results from errors
    valid_results = [r for r in results if not isinstance(r, Exception)]

    if not valid_results:
        # All failed — return safe default
        return ConsensusResult(
            classification=Complexity.STANDARD,
            confidence=0.0,
            vote_distribution={},
            total_voters=n_voters,
            valid_votes=0,
            consensus_reached=False,
        )

    # Count votes
    votes = [r.complexity for r in valid_results]
    distribution = dict(Counter(votes))

    # Find winner
    winner, count = Counter(votes).most_common(1)[0]
    confidence = count / len(valid_results)

    # Check if threshold met
    consensus_reached = confidence >= threshold

    # If no consensus, fall back to STANDARD
    if not consensus_reached:
        winner = Complexity.STANDARD

    return ConsensusResult(
        classification=winner,
        confidence=confidence,
        vote_distribution=distribution,
        total_voters=n_voters,
        valid_votes=len(valid_results),
        consensus_reached=consensus_reached,
    )


async def consensus_decision(
    prompt: str,
    options: list[str],
    model: ModelProtocol,
    n_voters: int = 5,
    threshold: float = 0.6,
    parallel: bool = False,
) -> ConsensusResult[str]:
    """Generic consensus voting for any decision.

    Ask N models to choose from options, return consensus.
    Sequential by default for local Ollama compatibility.

    Args:
        prompt: The decision prompt
        options: List of valid options
        model: The model to use
        n_voters: Number of voters
        threshold: Required agreement ratio
        parallel: Run calls in parallel (requires Ollama parallel support)

    Returns:
        ConsensusResult with chosen option
    """
    from sunwell.models.protocol import GenerateOptions

    options_str = ", ".join(options)
    full_prompt = f"""{prompt}

Choose exactly ONE of: {options_str}

Respond with only the chosen option, nothing else."""

    async def single_vote() -> str | None:
        try:
            result = await model.generate(
                full_prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=20),
            )
            # Extract the option from response
            response = result.text.strip().lower()
            for opt in options:
                if opt.lower() in response:
                    return opt
            return None
        except Exception:
            return None

    # Sequential by default (local Ollama friendly)
    if parallel:
        votes = await asyncio.gather(*[single_vote() for _ in range(n_voters)])
    else:
        votes = [await single_vote() for _ in range(n_voters)]

    # Filter valid votes
    valid_votes = [v for v in votes if v is not None]

    if not valid_votes:
        return ConsensusResult(
            classification=options[0],  # Default to first option
            confidence=0.0,
            vote_distribution={},
            total_voters=n_voters,
            valid_votes=0,
            consensus_reached=False,
        )

    # Count and determine winner
    distribution = dict(Counter(valid_votes))
    winner, count = Counter(valid_votes).most_common(1)[0]
    confidence = count / len(valid_votes)

    return ConsensusResult(
        classification=winner if confidence >= threshold else options[0],
        confidence=confidence,
        vote_distribution=distribution,
        total_voters=n_voters,
        valid_votes=len(valid_votes),
        consensus_reached=confidence >= threshold,
    )


# =============================================================================
# Convenience functions
# =============================================================================


async def should_use_tools(
    goal: str,
    model: ModelProtocol,
    n_voters: int = 5,
) -> tuple[bool, float]:
    """Consensus vote: Does this goal need tools?

    Returns:
        Tuple of (needs_tools, confidence)
    """
    result = await consensus_decision(
        prompt=f"Goal: {goal}\n\nDoes this goal require file operations, shell commands, or other tools to complete?",
        options=["yes", "no"],
        model=model,
        n_voters=n_voters,
    )

    return result.classification == "yes", result.confidence


async def should_use_harmonic(
    goal: str,
    model: ModelProtocol,
    n_voters: int = 5,
) -> tuple[bool, float]:
    """Consensus vote: Does this goal benefit from multiple perspectives?

    Returns:
        Tuple of (use_harmonic, confidence)
    """
    result = await consensus_decision(
        prompt=f"Goal: {goal}\n\nWould this goal benefit from multiple expert perspectives (critic, expert, user advocate) or is a single perspective sufficient?",
        options=["multiple", "single"],
        model=model,
        n_voters=n_voters,
    )

    return result.classification == "multiple", result.confidence
