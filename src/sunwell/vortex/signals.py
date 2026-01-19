"""Compressed signal format for efficient model communication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import GenerateOptions, ModelProtocol


@dataclass(frozen=True, slots=True)
class Signal:
    """A compressed thought signal.

    Signals are the communication primitive for vortex.
    They force clarity: one claim, explicit confidence, semantic tags.
    """

    claim: str
    """The core idea (max ~50 chars)."""

    confidence: float
    """Self-assessed confidence (0.0-1.0)."""

    tags: tuple[str, ...]
    """Semantic tags (max 5)."""

    source_island: int = 0
    """Which island this signal originated from."""

    source_agent: int = 0
    """Which agent within the island."""

    generation: int = 0
    """Which generation/iteration."""

    agreement: int = 0
    """How many other signals agreed with this one."""


# =============================================================================
# Prompts
# =============================================================================


SIGNAL_PROMPT = """Task: {task}

Output ONLY (no prose):
CLAIM: [max 12 words]
CONF: [0.0-1.0]
TAGS: [3-5 keywords, comma-separated]"""


REACT_PROMPT = """Task: {task}

Other signals:
{others}

React (ONLY this format):
AGREE: [count of signals you agree with]
CLAIM: [your updated claim, max 12 words]
CONF: [0.0-1.0]
TAGS: [3-5 keywords]"""


SELECTION_PROMPT = """Task: {task}

Candidate signals:
{candidates}

Pick the BEST. One sentence why.

Format:
PICK: [number]
WHY: [one sentence]"""


SYNTHESIS_PROMPT = """Task: {task}

Winning signal: {winner}
Selection reason: {reason}

Provide a COMPLETE response. Expand with:
- Specific details
- Trade-offs
- Examples

Response:"""


# =============================================================================
# Parsing
# =============================================================================


def parse_signal(
    text: str,
    island: int = 0,
    agent: int = 0,
    generation: int = 0,
) -> Signal:
    """Parse a compressed signal from model output."""
    claim_match = re.search(r"CLAIM:\s*(.+?)(?:\n|CONF:|$)", text, re.IGNORECASE)
    conf_match = re.search(r"CONF:\s*([\d.]+)", text, re.IGNORECASE)
    tags_match = re.search(r"TAGS:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    agree_match = re.search(r"AGREE:\s*(\d+)", text, re.IGNORECASE)

    claim = claim_match.group(1).strip()[:80] if claim_match else text[:80]

    try:
        conf = float(conf_match.group(1)) if conf_match else 0.5
    except ValueError:
        conf = 0.5

    tags_str = tags_match.group(1) if tags_match else ""
    tags = tuple(t.strip() for t in tags_str.split(",") if t.strip())[:5]

    agree = int(agree_match.group(1)) if agree_match else 0

    return Signal(
        claim=claim,
        confidence=min(1.0, max(0.0, conf)),
        tags=tags,
        source_island=island,
        source_agent=agent,
        generation=generation,
        agreement=agree,
    )


def parse_selection(text: str) -> tuple[int, str]:
    """Parse selection result (pick number and reason)."""
    pick_match = re.search(r"PICK:\s*(\d+)", text, re.IGNORECASE)
    why_match = re.search(r"WHY:\s*(.+?)(?:\n|$)", text, re.IGNORECASE | re.DOTALL)

    pick = int(pick_match.group(1)) - 1 if pick_match else 0
    reason = why_match.group(1).strip() if why_match else "Selected as best candidate."

    return pick, reason


# =============================================================================
# Generation
# =============================================================================


async def generate_signal(
    task: str,
    model: ModelProtocol,
    options: GenerateOptions,
    island: int = 0,
    agent: int = 0,
    generation: int = 0,
) -> Signal:
    """Generate a single compressed signal."""
    result = await model.generate(
        SIGNAL_PROMPT.format(task=task),
        options=options,
    )
    return parse_signal(result.text, island, agent, generation)


async def generate_reaction(
    task: str,
    others: list[Signal],
    model: ModelProtocol,
    options: GenerateOptions,
    island: int = 0,
    agent: int = 0,
    generation: int = 0,
) -> Signal:
    """Generate a reaction to other signals."""
    others_str = "\n".join(
        f"{i+1}. [{s.confidence:.1f}] {s.claim}"
        for i, s in enumerate(others)
    )

    result = await model.generate(
        REACT_PROMPT.format(task=task, others=others_str),
        options=options,
    )
    return parse_signal(result.text, island, agent, generation)


def format_signal(signal: Signal) -> str:
    """Format a signal for display."""
    tags = ", ".join(signal.tags) if signal.tags else "none"
    return f"[{signal.confidence:.1f}, +{signal.agreement}] {signal.claim} ({tags})"
