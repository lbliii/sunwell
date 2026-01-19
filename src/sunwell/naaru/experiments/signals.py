"""LLM Signal Protocol — Compressed inter-model communication.

The hypothesis: LLMs communicating via natural language is expensive and lossy.
Like neurons or ants, they should signal with minimal, structured messages.

Signal Types:
    - Trit (0, 1, 2): No / Maybe / Yes
    - Flags: Boolean feature vectors
    - Scores: Continuous 0.0-1.0
    - Enums: Discrete categories
    - Traces: Stigmergy (leave marks for others)

The network effect emerges from many simple signals, not complex paragraphs.

Example:
    >>> from sunwell.naaru.experiments.signals import SignalNetwork
    >>>
    >>> network = SignalNetwork(model)
    >>> result = await network.evaluate("Build a REST API")
    >>> print(result.signals)  # {'complex': 2, 'tools': 1, 'safe': 0}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


class Trit(IntEnum):
    """Ternary signal: No / Maybe / Yes."""
    NO = 0
    MAYBE = 1
    YES = 2

    def __bool__(self) -> bool:
        return self != Trit.NO

    @classmethod
    def from_text(cls, text: str) -> Trit:
        """Parse trit from LLM response."""
        t = text.strip().upper()
        if t in ("0", "NO", "FALSE", "NEGATIVE", "N"):
            return cls.NO
        if t in ("2", "YES", "TRUE", "POSITIVE", "Y"):
            return cls.YES
        return cls.MAYBE  # Default to uncertain


class Signal(IntEnum):
    """Action signals."""
    SKIP = 0       # Don't do this
    PROCEED = 1    # Continue normally
    ESCALATE = 2   # Needs more attention


@dataclass(frozen=True, slots=True)
class SignalVector:
    """A vector of signals — like a feature vector for the task."""

    complexity: Trit = Trit.MAYBE
    """Is this complex? 0=simple, 1=moderate, 2=complex"""

    needs_tools: Trit = Trit.MAYBE
    """Does this need file/shell tools?"""

    needs_context: Trit = Trit.MAYBE
    """Does this need project context?"""

    is_dangerous: Trit = Trit.NO
    """Could this cause harm? (delete files, etc)"""

    is_ambiguous: Trit = Trit.MAYBE
    """Is the goal unclear?"""

    confidence: float = 0.5
    """Overall confidence in the signals."""

    def to_bits(self) -> tuple[int, ...]:
        """Convert to raw bit representation."""
        return (
            self.complexity.value,
            self.needs_tools.value,
            self.needs_context.value,
            self.is_dangerous.value,
            self.is_ambiguous.value,
        )

    def __repr__(self) -> str:
        bits = "".join(str(b) for b in self.to_bits())
        return f"SignalVector({bits}, conf={self.confidence:.0%})"


@dataclass
class SignalTrace:
    """A trace left in shared memory (stigmergy pattern).

    Like ants leaving pheromones — signals that persist and
    influence future model calls.
    """

    key: str
    """What this trace is about."""

    value: Trit
    """The signal value."""

    source: str
    """Which model/gate left this trace."""

    strength: float = 1.0
    """Trace strength (decays over time)."""

    def decay(self, rate: float = 0.9) -> SignalTrace:
        """Decay the trace strength."""
        return SignalTrace(
            key=self.key,
            value=self.value,
            source=self.source,
            strength=self.strength * rate,
        )


@dataclass
class SharedMemory:
    """Shared memory for stigmergy-based coordination.

    Models leave traces, other models read and react.
    Like an ant colony's pheromone network.
    """

    traces: dict[str, SignalTrace] = field(default_factory=dict)
    """Current traces in memory."""

    history: list[SignalTrace] = field(default_factory=list)
    """All traces ever left (for debugging)."""

    def leave_trace(self, key: str, value: Trit, source: str) -> None:
        """Leave a trace in shared memory."""
        trace = SignalTrace(key=key, value=value, source=source)
        self.traces[key] = trace
        self.history.append(trace)

    def read_trace(self, key: str) -> Trit | None:
        """Read a trace, returns None if not found."""
        trace = self.traces.get(key)
        return trace.value if trace else None

    def decay_all(self, rate: float = 0.9) -> None:
        """Decay all traces, remove weak ones."""
        self.traces = {
            k: t.decay(rate)
            for k, t in self.traces.items()
            if t.strength * rate > 0.1
        }

    def summary(self) -> dict[str, int]:
        """Get summary of current trace values."""
        return {k: t.value for k, t in self.traces.items()}


# =============================================================================
# Signal Extraction
# =============================================================================


async def extract_signals(
    goal: str,
    model: ModelProtocol,
) -> SignalVector:
    """Extract signal vector from goal using individual trit questions.

    Uses the simplest possible prompts — one question per signal.
    Like asking a neuron: fire or not?

    Args:
        goal: The goal to analyze
        model: The model to use

    Returns:
        SignalVector with extracted signals
    """
    # Ask each question individually — tiny models handle this better
    complexity = await trit_classify(goal, "Is this task complex?", model)
    needs_tools = await trit_classify(goal, "Does this need file or shell operations?", model)
    needs_context = await trit_classify(goal, "Does this need project context?", model)
    is_dangerous = await trit_classify(goal, "Could this cause harm (delete files, break things)?", model)
    is_ambiguous = await trit_classify(goal, "Is this goal unclear or ambiguous?", model)

    return SignalVector(
        complexity=complexity,
        needs_tools=needs_tools,
        needs_context=needs_context,
        is_dangerous=is_dangerous,
        is_ambiguous=is_ambiguous,
        confidence=0.8,
    )


# =============================================================================
# Signal Network
# =============================================================================


@dataclass
class SignalNetwork:
    """A network of models communicating via signals.

    Models don't pass paragraphs to each other — they pass signals.
    The network coordinates through these compressed messages.
    """

    model: ModelProtocol
    """The model to use for signal extraction."""

    memory: SharedMemory = field(default_factory=SharedMemory)
    """Shared memory for stigmergy."""

    async def evaluate(self, goal: str) -> SignalVector:
        """Evaluate a goal and extract signals."""
        signals = await extract_signals(goal, self.model)

        # Leave traces in shared memory
        self.memory.leave_trace("last_complexity", signals.complexity, "evaluator")
        self.memory.leave_trace("last_tools", signals.needs_tools, "evaluator")

        return signals

    async def route(self, goal: str) -> Signal:
        """Route a goal based on signals.

        Returns:
            SKIP: Goal is trivial or invalid
            PROCEED: Normal processing
            ESCALATE: Needs special attention
        """
        signals = await self.evaluate(goal)

        # Simple routing logic based on signals
        if signals.is_dangerous == Trit.YES:
            return Signal.ESCALATE

        if signals.complexity == Trit.NO and signals.needs_tools == Trit.NO:
            return Signal.SKIP  # Too simple, maybe just answer directly

        if signals.complexity == Trit.YES or signals.is_ambiguous == Trit.YES:
            return Signal.ESCALATE

        return Signal.PROCEED


# =============================================================================
# Multi-Gate Signal Coordination
# =============================================================================


async def signal_cascade(
    goal: str,
    gates: list[ModelProtocol],
) -> tuple[SignalVector, list[SignalVector]]:
    """Run goal through multiple gates, accumulating signals.

    Each gate adds its perspective to the signal vector.
    Like multiple neurons contributing to a decision.

    Args:
        goal: The goal to evaluate
        gates: List of models (gates) to consult

    Returns:
        Tuple of (aggregated_signals, individual_signals)
    """
    all_signals: list[SignalVector] = []

    for gate in gates:
        signals = await extract_signals(goal, gate)
        all_signals.append(signals)

    # Aggregate signals (simple voting for now)
    def aggregate_trit(values: list[Trit]) -> Trit:
        avg = sum(v.value for v in values) / len(values)
        if avg < 0.5:
            return Trit.NO
        if avg > 1.5:
            return Trit.YES
        return Trit.MAYBE

    aggregated = SignalVector(
        complexity=aggregate_trit([s.complexity for s in all_signals]),
        needs_tools=aggregate_trit([s.needs_tools for s in all_signals]),
        needs_context=aggregate_trit([s.needs_context for s in all_signals]),
        is_dangerous=aggregate_trit([s.is_dangerous for s in all_signals]),
        is_ambiguous=aggregate_trit([s.is_ambiguous for s in all_signals]),
        confidence=sum(s.confidence for s in all_signals) / len(all_signals),
    )

    return aggregated, all_signals


# =============================================================================
# Binary Protocol Experiments
# =============================================================================


async def binary_classify(
    goal: str,
    question: str,
    model: ModelProtocol,
) -> bool:
    """Single binary signal: Yes or No.

    The most compressed form of LLM-to-LLM communication.

    Args:
        goal: The goal being evaluated
        question: Yes/No question about the goal
        model: The model to use

    Returns:
        True for Yes, False for No
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = f"""Goal: {goal}

Question: {question}

Answer with ONLY: YES or NO"""

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.0, max_tokens=5),
    )

    return "yes" in result.text.lower()


async def trit_classify(
    goal: str,
    question: str,
    model: ModelProtocol,
) -> Trit:
    """Ternary signal: No / Maybe / Yes.

    Adds uncertainty as a first-class signal.

    Args:
        goal: The goal being evaluated
        question: Question about the goal
        model: The model to use

    Returns:
        Trit value
    """
    from sunwell.models.protocol import GenerateOptions

    prompt = f"""Goal: {goal}

Question: {question}

Answer with ONLY one of: NO, MAYBE, YES"""

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.0, max_tokens=5),
    )

    return Trit.from_text(result.text)
