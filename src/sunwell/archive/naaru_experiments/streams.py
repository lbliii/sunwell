"""Signal Streams — Per-chunk micro-classification.

The hypothesis: A single classification for the whole input loses information.
Instead, emit a STREAM of signals over chunks of the input.

Like:
- Per-pixel classification in image segmentation
- Token-level attention in transformers
- Line-by-line code review

Examples:
    Goal: "Create REST API with auth that deletes user data"

    Chunk stream:
        "Create REST API"    → 1 (standard)
        "with auth"          → 2 (complex)
        "deletes user data"  → 2 (DANGER!)
                               ─────────
    Stream: [1, 2, 2]

    Code review:
        line 1: import os     → 0 (fine)
        line 2: x = input()   → 1 (maybe unsafe)
        line 3: os.system(x)  → 2 (DANGER!)
                                ─────────
    Stream: [0, 1, 2]

The stream reveals WHERE the complexity/danger lives, not just IF it exists.
"""


from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.archive.naaru_experiments.signals import Trit

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


@dataclass(frozen=True, slots=True)
class ChunkSignal:
    """A single chunk with its signal."""

    chunk: str
    """The text chunk."""

    signal: Trit
    """The signal for this chunk (0/1/2)."""

    index: int
    """Position in the stream."""

    def __repr__(self) -> str:
        return f"[{self.signal.value}] {self.chunk[:40]}..."


@dataclass(frozen=True, slots=True)
class SignalStream:
    """A stream of signals over chunks."""

    chunks: tuple[ChunkSignal, ...]
    """The chunk signals in order."""

    question: str
    """What question was asked about each chunk."""

    @property
    def values(self) -> tuple[int, ...]:
        """Raw signal values as tuple."""
        return tuple(c.signal.value for c in self.chunks)

    @property
    def max_signal(self) -> Trit:
        """Highest signal in stream (most concerning)."""
        if not self.chunks:
            return Trit.NO
        return Trit(max(c.signal.value for c in self.chunks))

    @property
    def hot_chunks(self) -> tuple[ChunkSignal, ...]:
        """Chunks with signal=2 (YES/HIGH)."""
        return tuple(c for c in self.chunks if c.signal == Trit.YES)

    @property
    def warm_chunks(self) -> tuple[ChunkSignal, ...]:
        """Chunks with signal>=1 (MAYBE or YES)."""
        return tuple(c for c in self.chunks if c.signal >= Trit.MAYBE)

    def __repr__(self) -> str:
        bits = "".join(str(c.signal.value) for c in self.chunks)
        return f"SignalStream({bits})"

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"Stream: {self!r}"]
        for chunk in self.chunks:
            marker = (
                "🔴" if chunk.signal == Trit.YES
                else "🟡" if chunk.signal == Trit.MAYBE
                else "⚪"
            )
            lines.append(f"  {marker} [{chunk.signal.value}] {chunk.chunk}")
        return "\n".join(lines)


# =============================================================================
# Chunking Strategies
# =============================================================================


def chunk_by_sentence(text: str) -> list[str]:
    """Split text into sentences."""
    import re
    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_by_line(text: str) -> list[str]:
    """Split text into lines."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def chunk_by_clause(text: str) -> list[str]:
    """Split text into clauses (by commas, semicolons, conjunctions)."""
    import re
    # Split on clause boundaries
    clauses = re.split(r'[,;]|\s+(?:and|or|but|that|which|with)\s+', text)
    return [c.strip() for c in clauses if c.strip() and len(c.strip()) > 3]


def chunk_by_step(text: str) -> list[str]:
    """Split text into numbered steps."""
    import re
    # Find numbered items
    steps = re.split(r'\d+[.)]\s*', text)
    return [s.strip() for s in steps if s.strip()]


# =============================================================================
# Stream Classification
# =============================================================================


async def classify_stream(
    chunks: Sequence[str],
    question: str,
    model: ModelProtocol,
) -> SignalStream:
    """Classify each chunk with a trit signal.

    Args:
        chunks: The chunks to classify
        question: The question to ask about each chunk
        model: The model to use

    Returns:
        SignalStream with per-chunk signals
    """
    from sunwell.archive.naaru_experiments.signals import trit_classify

    signals: list[ChunkSignal] = []

    for i, chunk in enumerate(chunks):
        trit = await trit_classify(chunk, question, model)
        signals.append(ChunkSignal(chunk=chunk, signal=trit, index=i))

    return SignalStream(chunks=tuple(signals), question=question)


async def danger_scan(
    text: str,
    model: ModelProtocol,
    chunker: callable = chunk_by_clause,
) -> SignalStream:
    """Scan text for dangerous operations.

    Returns stream highlighting WHERE danger lives.

    Args:
        text: The text to scan
        model: The model to use
        chunker: How to split the text

    Returns:
        SignalStream with danger signals
    """
    chunks = chunker(text)
    return await classify_stream(
        chunks,
        question="Could this cause harm, data loss, or security issues?",
        model=model,
    )


async def complexity_scan(
    text: str,
    model: ModelProtocol,
    chunker: callable = chunk_by_clause,
) -> SignalStream:
    """Scan text for complexity hotspots.

    Returns stream highlighting WHERE complexity lives.
    """
    chunks = chunker(text)
    return await classify_stream(
        chunks,
        question="Is this part complex or difficult?",
        model=model,
    )


async def code_review_stream(
    code: str,
    model: ModelProtocol,
) -> SignalStream:
    """Review code line-by-line for issues.

    Returns stream highlighting problematic lines.
    """
    lines = chunk_by_line(code)
    return await classify_stream(
        lines,
        question="Does this line have bugs, security issues, or bad practices?",
        model=model,
    )


async def claim_verification_stream(
    document: str,
    model: ModelProtocol,
) -> SignalStream:
    """Verify claims in a document sentence-by-sentence.

    Returns stream highlighting unverified claims.
    """
    sentences = chunk_by_sentence(document)
    return await classify_stream(
        sentences,
        question="Is this claim verifiable and likely accurate?",
        model=model,
    )


# =============================================================================
# Stream Aggregation
# =============================================================================


def aggregate_streams(*streams: SignalStream) -> dict[str, int]:
    """Aggregate multiple streams into summary stats.

    Args:
        streams: Multiple signal streams

    Returns:
        Dict with aggregated statistics
    """
    all_signals = []
    for stream in streams:
        all_signals.extend(c.signal.value for c in stream.chunks)

    if not all_signals:
        return {"total": 0, "hot": 0, "warm": 0, "cold": 0, "max": 0}

    return {
        "total": len(all_signals),
        "hot": sum(1 for s in all_signals if s == 2),  # YES/HIGH
        "warm": sum(1 for s in all_signals if s == 1),  # MAYBE
        "cold": sum(1 for s in all_signals if s == 0),  # NO
        "max": max(all_signals),
        "mean": sum(all_signals) / len(all_signals),
    }


def merge_streams(
    stream_a: SignalStream,
    stream_b: SignalStream,
) -> SignalStream:
    """Merge two streams, taking max signal per chunk.

    Useful when multiple questions are asked about the same chunks.
    """
    if len(stream_a.chunks) != len(stream_b.chunks):
        raise ValueError("Streams must have same number of chunks")

    merged = []
    for a, b in zip(stream_a.chunks, stream_b.chunks, strict=True):
        max_signal = Trit(max(a.signal.value, b.signal.value))
        merged.append(ChunkSignal(
            chunk=a.chunk,
            signal=max_signal,
            index=a.index,
        ))

    return SignalStream(
        chunks=tuple(merged),
        question=f"({stream_a.question}) OR ({stream_b.question})",
    )


# =============================================================================
# Multi-Question Streams
# =============================================================================


async def multi_scan(
    text: str,
    questions: dict[str, str],
    model: ModelProtocol,
    chunker: callable = chunk_by_clause,
) -> dict[str, SignalStream]:
    """Scan text with multiple questions, returning streams for each.

    Args:
        text: The text to scan
        questions: Dict of {name: question}
        model: The model to use
        chunker: How to split the text

    Returns:
        Dict of {name: SignalStream}
    """
    chunks = chunker(text)

    results = {}
    for name, question in questions.items():
        stream = await classify_stream(chunks, question, model)
        results[name] = stream

    return results


async def comprehensive_scan(
    text: str,
    model: ModelProtocol,
) -> dict[str, SignalStream]:
    """Scan text for multiple dimensions at once.

    Returns streams for: danger, complexity, ambiguity, tools_needed
    """
    return await multi_scan(
        text,
        questions={
            "danger": "Could this cause harm or data loss?",
            "complexity": "Is this complex or difficult?",
            "ambiguity": "Is this unclear or ambiguous?",
            "tools": "Does this need file/shell operations?",
        },
        model=model,
    )
