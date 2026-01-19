"""Extraction patterns for grounded information retrieval.

Squash Extraction:
- Multiple extractions per question (for agreement)
- Agreement → High confidence
- Disagreement → Flag for review
- Synthesis from confident facts only

Unlike naive extraction which can hallucinate,
squash extraction grounds outputs in document agreement.
"""

from sunwell.extraction.squash import (
    ExtractedFact,
    SquashResult,
    extract_goal_with_squash,
    squash_extract,
)

__all__ = [
    "ExtractedFact",
    "SquashResult",
    "extract_goal_with_squash",
    "squash_extract",
]
