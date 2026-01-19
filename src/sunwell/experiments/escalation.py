"""Signal Accumulation & Selective Escalation.

The hypothesis: Most chunks are easy (0/1). Only escalate the hard ones (2).
This routes 90%+ of work to tiny models, reserving big models for what matters.

Patterns:
    1. Accumulator: Running signal total, trigger on threshold
    2. Selective Escalation: Route only hot chunks to bigger models
    3. Heat Map: Visualize where complexity/danger concentrates
    4. Cascade Triage: Tiny → Medium → Large based on accumulated signals

Example:
    >>> stream = await danger_scan(code, tiny_model)
    >>> # Stream: [0,0,1,0,2,0,0,2,0,0]
    >>> #              ↑     ↑
    >>> # Only these chunks go to big model
    >>>
    >>> refined = await escalate_hot_chunks(stream, big_model)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.experiments.signals import Trit
from sunwell.experiments.streams import ChunkSignal, SignalStream

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Signal Accumulator
# =============================================================================


@dataclass
class SignalAccumulator:
    """Accumulates signals over time, triggers on thresholds.

    Like a capacitor that fires when charge exceeds threshold.
    """

    threshold: float = 3.0
    """Accumulated value that triggers escalation."""

    decay: float = 0.9
    """How fast old signals decay (0-1)."""

    _accumulated: float = field(default=0.0, init=False)
    """Current accumulated value."""

    _history: list[tuple[str, Trit]] = field(default_factory=list, init=False)
    """History of (chunk, signal) pairs."""

    def add(self, chunk: str, signal: Trit) -> bool:
        """Add a signal, return True if threshold exceeded.

        Args:
            chunk: The chunk that produced this signal
            signal: The signal value (0/1/2)

        Returns:
            True if accumulated value exceeds threshold
        """
        # Decay existing accumulated value
        self._accumulated *= self.decay

        # Add new signal
        self._accumulated += signal.value

        # Track history
        self._history.append((chunk, signal))

        return self._accumulated >= self.threshold

    def add_stream(self, stream: SignalStream) -> list[int]:
        """Add a stream, return indices where threshold was exceeded.

        Args:
            stream: The signal stream

        Returns:
            List of chunk indices where escalation triggered
        """
        triggers = []
        for i, chunk_signal in enumerate(stream.chunks):
            if self.add(chunk_signal.chunk, chunk_signal.signal):
                triggers.append(i)
        return triggers

    @property
    def value(self) -> float:
        """Current accumulated value."""
        return self._accumulated

    @property
    def hot(self) -> bool:
        """Whether currently above threshold."""
        return self._accumulated >= self.threshold

    def reset(self) -> None:
        """Reset accumulated value."""
        self._accumulated = 0.0


# =============================================================================
# Selective Escalation
# =============================================================================


@dataclass(frozen=True, slots=True)
class EscalationResult:
    """Result from selective escalation."""

    original_stream: SignalStream
    """The original stream from tiny model."""

    escalated_chunks: tuple[ChunkSignal, ...]
    """Chunks that were escalated to big model."""

    refined_signals: tuple[ChunkSignal, ...]
    """Refined signals from big model."""

    final_stream: SignalStream
    """Final stream with refined signals merged in."""

    escalation_rate: float
    """Fraction of chunks that needed escalation."""

    @property
    def savings(self) -> float:
        """Compute saved: 1 - escalation_rate."""
        return 1.0 - self.escalation_rate


async def escalate_hot_chunks(
    stream: SignalStream,
    big_model: ModelProtocol,
    threshold: Trit = Trit.YES,
) -> EscalationResult:
    """Escalate only hot chunks to a bigger model.

    Tiny model scans everything. Big model only sees the hot chunks.

    Args:
        stream: Signal stream from tiny model
        big_model: Bigger model for refinement
        threshold: Minimum signal to escalate (default: YES/2)

    Returns:
        EscalationResult with refined signals
    """
    from sunwell.experiments.signals import trit_classify

    # Find chunks that need escalation
    hot_chunks = [c for c in stream.chunks if c.signal >= threshold]

    if not hot_chunks:
        # Nothing to escalate
        return EscalationResult(
            original_stream=stream,
            escalated_chunks=(),
            refined_signals=(),
            final_stream=stream,
            escalation_rate=0.0,
        )

    # Refine hot chunks with big model
    refined: list[ChunkSignal] = []
    for chunk in hot_chunks:
        # Re-classify with big model
        new_signal = await trit_classify(
            chunk.chunk,
            stream.question,
            big_model,
        )
        refined.append(ChunkSignal(
            chunk=chunk.chunk,
            signal=new_signal,
            index=chunk.index,
        ))

    # Merge refined signals into original stream
    refined_by_index = {r.index: r for r in refined}
    final_chunks = []
    for chunk in stream.chunks:
        if chunk.index in refined_by_index:
            final_chunks.append(refined_by_index[chunk.index])
        else:
            final_chunks.append(chunk)

    final_stream = SignalStream(
        chunks=tuple(final_chunks),
        question=stream.question,
    )

    return EscalationResult(
        original_stream=stream,
        escalated_chunks=tuple(hot_chunks),
        refined_signals=tuple(refined),
        final_stream=final_stream,
        escalation_rate=len(hot_chunks) / len(stream.chunks),
    )


async def cascade_triage(
    text: str,
    question: str,
    models: list[ModelProtocol],
    chunker: callable | None = None,
) -> SignalStream:
    """Cascade through models: tiny scans all, medium refines warm, large refines hot.

    Like medical triage:
    - Nurse (tiny): Quick screen everyone
    - Doctor (medium): Examine concerning cases
    - Specialist (large): Deep dive on critical cases

    Args:
        text: The text to analyze
        question: The question to ask
        models: List of models [tiny, medium, large]
        chunker: How to split text (default: by clause)

    Returns:
        Final SignalStream after cascade refinement
    """
    from sunwell.experiments.streams import chunk_by_clause, classify_stream

    if chunker is None:
        chunker = chunk_by_clause

    chunks = chunker(text)

    if len(models) < 1:
        raise ValueError("Need at least one model")

    # Stage 1: Tiny model scans everything
    stream = await classify_stream(chunks, question, models[0])

    if len(models) < 2:
        return stream

    # Stage 2: Medium model refines warm chunks (signal >= 1)
    warm_chunks = [c for c in stream.chunks if c.signal >= Trit.MAYBE]

    if warm_chunks and len(models) >= 2:
        from sunwell.experiments.signals import trit_classify

        refined_warm = {}
        for chunk in warm_chunks:
            new_signal = await trit_classify(chunk.chunk, question, models[1])
            refined_warm[chunk.index] = new_signal

        # Update stream
        new_chunks = []
        for chunk in stream.chunks:
            if chunk.index in refined_warm:
                new_chunks.append(ChunkSignal(
                    chunk=chunk.chunk,
                    signal=refined_warm[chunk.index],
                    index=chunk.index,
                ))
            else:
                new_chunks.append(chunk)

        stream = SignalStream(chunks=tuple(new_chunks), question=question)

    if len(models) < 3:
        return stream

    # Stage 3: Large model refines hot chunks (signal == 2)
    hot_chunks = [c for c in stream.chunks if c.signal == Trit.YES]

    if hot_chunks:
        from sunwell.experiments.signals import trit_classify

        refined_hot = {}
        for chunk in hot_chunks:
            new_signal = await trit_classify(chunk.chunk, question, models[2])
            refined_hot[chunk.index] = new_signal

        # Update stream
        new_chunks = []
        for chunk in stream.chunks:
            if chunk.index in refined_hot:
                new_chunks.append(ChunkSignal(
                    chunk=chunk.chunk,
                    signal=refined_hot[chunk.index],
                    index=chunk.index,
                ))
            else:
                new_chunks.append(chunk)

        stream = SignalStream(chunks=tuple(new_chunks), question=question)

    return stream


# =============================================================================
# Heat Map
# =============================================================================


def render_heat_map(stream: SignalStream, width: int = 50) -> str:
    """Render stream as ASCII heat map.

    Shows where the "heat" (high signals) concentrates.

    Args:
        stream: The signal stream
        width: Width of the visualization

    Returns:
        ASCII heat map string
    """
    if not stream.chunks:
        return "Empty stream"

    lines = []

    # Header
    lines.append(f"Heat Map: {stream!r}")
    lines.append("─" * width)

    # Per-chunk bars
    for chunk in stream.chunks:
        # Signal indicator
        if chunk.signal == Trit.YES:
            indicator = "🔴"
            bar_char = "█"
        elif chunk.signal == Trit.MAYBE:
            indicator = "🟡"
            bar_char = "▓"
        else:
            indicator = "⚪"
            bar_char = "░"

        # Truncate chunk text
        text = chunk.chunk[:30].ljust(30)

        # Bar length proportional to signal
        bar_len = (chunk.signal.value + 1) * 5
        bar = bar_char * bar_len

        lines.append(f"{indicator} {text} {bar}")

    # Footer with stats
    lines.append("─" * width)
    hot = len([c for c in stream.chunks if c.signal == Trit.YES])
    warm = len([c for c in stream.chunks if c.signal == Trit.MAYBE])
    cold = len([c for c in stream.chunks if c.signal == Trit.NO])
    lines.append(f"🔴 Hot: {hot}  🟡 Warm: {warm}  ⚪ Cold: {cold}")

    return "\n".join(lines)


# =============================================================================
# Threshold-Based Actions
# =============================================================================


@dataclass
class ThresholdAction:
    """Action to take when accumulated signal crosses threshold."""

    threshold: float
    """Signal threshold."""

    action: str
    """Action name (for logging/routing)."""

    callback: callable | None = None
    """Optional callback to execute."""


async def threshold_scan(
    text: str,
    question: str,
    model: ModelProtocol,
    actions: list[ThresholdAction],
    chunker: callable | None = None,
) -> list[tuple[int, str]]:
    """Scan text and trigger actions when thresholds crossed.

    Args:
        text: Text to scan
        question: Question to ask per chunk
        model: Model to use
        actions: List of threshold actions (sorted by threshold)
        chunker: How to split text

    Returns:
        List of (chunk_index, action_name) pairs that triggered
    """
    from sunwell.experiments.streams import chunk_by_clause

    if chunker is None:
        chunker = chunk_by_clause

    chunks = chunker(text)

    # Sort actions by threshold
    sorted_actions = sorted(actions, key=lambda a: a.threshold)

    accumulator = SignalAccumulator(threshold=sorted_actions[0].threshold)

    triggers: list[tuple[int, str]] = []

    from sunwell.experiments.signals import trit_classify

    for i, chunk in enumerate(chunks):
        signal = await trit_classify(chunk, question, model)

        # Check each threshold
        for action in sorted_actions:
            accumulator.threshold = action.threshold
            if accumulator.add(chunk, signal):
                triggers.append((i, action.action))
                if action.callback:
                    action.callback(i, chunk, signal)

    return triggers
