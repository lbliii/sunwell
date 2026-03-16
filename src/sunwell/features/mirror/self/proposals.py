"""ProposalManager stub (mirror feature removed)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Proposal:
    """Minimal Proposal stub."""

    id: str
    description: str


class ProposalManager:
    """No-op stub."""
