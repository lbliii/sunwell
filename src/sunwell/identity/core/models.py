"""Identity core models - Identity and Observation dataclasses.

RFC-023: Two-level storage for identity data:
- Session-specific: .sunwell/memory/sessions/{session}_identity.yaml
- Global fallback: ~/.sunwell/global_identity.yaml

Supports:
- Observation tracking with timestamps and confidence
- Adaptive digest frequency based on observation density
- Session carry-forward from global identity
"""

from dataclasses import dataclass, field
from datetime import datetime

from sunwell.identity.core.constants import MIN_IDENTITY_CONFIDENCE


@dataclass(slots=True)
class Observation:
    """A behavioral observation about the user."""

    timestamp: datetime
    observation: str
    confidence: float = 0.8
    turn_id: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "observation": self.observation,
            "confidence": self.confidence,
            "turn_id": self.turn_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Observation:
        """Deserialize from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            timestamp=timestamp,
            observation=data.get("observation", ""),
            confidence=data.get("confidence", 0.8),
            turn_id=data.get("turn_id"),
        )


@dataclass(slots=True)
class Identity:
    """User identity model with behavioral observations and synthesized prompt."""

    observations: list[Observation] = field(default_factory=list)
    tone: str | None = None
    pace: str | None = None
    values: list[str] = field(default_factory=list)
    prompt: str | None = None
    confidence: float = 0.0
    last_digest: datetime | None = None
    turn_count_at_digest: int = 0
    inherited: bool = False
    paused: bool = False  # If True, no new observations are recorded

    def is_usable(self) -> bool:
        """Returns True if identity should be injected into system prompt."""
        return (
            self.prompt is not None
            and len(self.prompt) > 10
            and self.confidence >= MIN_IDENTITY_CONFIDENCE
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "observations": [o.to_dict() for o in self.observations],
            "tone": self.tone,
            "pace": self.pace,
            "values": self.values,
            "prompt": self.prompt,
            "confidence": self.confidence,
            "last_digest": self.last_digest.isoformat() if self.last_digest else None,
            "turn_count_at_digest": self.turn_count_at_digest,
            "inherited": self.inherited,
            "paused": self.paused,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Identity:
        """Deserialize from dictionary."""
        observations = [
            Observation.from_dict(o) for o in data.get("observations", [])
        ]

        last_digest = data.get("last_digest")
        if isinstance(last_digest, str):
            last_digest = datetime.fromisoformat(last_digest)

        return cls(
            observations=observations,
            tone=data.get("tone"),
            pace=data.get("pace"),
            values=data.get("values", []),
            prompt=data.get("prompt"),
            confidence=data.get("confidence", 0.0),
            last_digest=last_digest,
            turn_count_at_digest=data.get("turn_count_at_digest", 0),
            inherited=data.get("inherited", False),
            paused=data.get("paused", False),
        )
