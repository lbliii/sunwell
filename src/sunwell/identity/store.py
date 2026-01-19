"""Identity storage with session and global persistence.

RFC-023: Two-level storage for identity data:
- Session-specific: .sunwell/memory/sessions/{session}_identity.yaml
- Global fallback: ~/.sunwell/global_identity.yaml

Supports:
- Observation tracking with timestamps and confidence
- Adaptive digest frequency based on observation density
- Session carry-forward from global identity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    pass


# Constants from RFC-023
MIN_IDENTITY_CONFIDENCE = 0.6
MAX_OBSERVATIONS_PER_SESSION = 50
MAX_OBSERVATIONS_GLOBAL = 100
MAX_IDENTITY_PROMPT_LENGTH = 500


@dataclass
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


@dataclass
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


class IdentityStore:
    """Manages identity storage with session and global persistence.

    Storage hierarchy:
    1. Session-specific identity (highest priority)
    2. Global identity (fallback, read-only inheritance)
    3. Fresh start (no identity)
    """

    def __init__(self, session_path: Path):
        """Initialize identity store.

        Args:
            session_path: Path to session directory (e.g., .sunwell/memory/sessions/xxx)
        """
        self.session_path = Path(session_path).with_suffix('.identity.yaml')
        self.global_path = Path.home() / ".sunwell" / "global_identity.yaml"
        self.identity = self._load()
        self._recent_observation_count = 0  # For adaptive digest frequency

    def _load(self) -> Identity:
        """Load identity with global fallback."""
        # 1. Try session-specific
        if self.session_path.exists():
            return self._load_yaml(self.session_path)

        # 2. Fall back to global (read-only inheritance)
        if self.global_path.exists():
            identity = self._load_yaml(self.global_path)
            identity.inherited = True
            return identity

        # 3. Fresh start
        return Identity()

    def _load_yaml(self, path: Path) -> Identity:
        """Load identity from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data is None:
                return Identity()
            return Identity.from_dict(data.get("identity", data))
        except Exception:
            return Identity()

    def _save(self) -> None:
        """Save identity to session file."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "identity": self.identity.to_dict(),
        }

        with open(self.session_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def add_observation(
        self,
        observation: str,
        confidence: float = 0.8,
        turn_id: str | None = None
    ) -> None:
        """Add a behavioral observation.

        Args:
            observation: The behavioral observation text
            confidence: Confidence score (0-1)
            turn_id: Optional turn ID this observation came from
        """
        if self.identity.paused:
            return

        self.identity.observations.append(Observation(
            timestamp=datetime.now(),
            observation=observation,
            confidence=confidence,
            turn_id=turn_id,
        ))

        # Keep only recent N for session
        self.identity.observations = self.identity.observations[-MAX_OBSERVATIONS_PER_SESSION:]
        self._recent_observation_count += 1
        self._save()

    def needs_digest(self, current_turn_count: int) -> bool:
        """Adaptive digest frequency based on observation density.

        Returns True if identity should be re-synthesized.
        """
        if self.identity.paused:
            return False

        if not self.identity.observations:
            return False

        turns_since_digest = current_turn_count - self.identity.turn_count_at_digest

        # Early session: establish baseline quickly
        if current_turn_count <= 5 and len(self.identity.observations) >= 3:
            return self.identity.last_digest is None

        # High activity: many behaviors in short window
        if self._recent_observation_count >= 5 and turns_since_digest >= 3:
            self._recent_observation_count = 0  # Reset counter
            return True

        # Normal cadence
        return turns_since_digest >= 10

    def update_digest(
        self,
        prompt: str,
        confidence: float,
        turn_count: int,
        tone: str | None = None,
        pace: str | None = None,
        values: list[str] | None = None,
    ) -> None:
        """Update identity with new digest results.

        Args:
            prompt: Synthesized identity prompt
            confidence: Digest confidence score
            turn_count: Current turn count
            tone: Detected tone preference
            pace: Detected pace preference
            values: List of detected values
        """
        self.identity.prompt = prompt
        self.identity.confidence = confidence
        self.identity.turn_count_at_digest = turn_count
        self.identity.last_digest = datetime.now()

        if tone:
            self.identity.tone = tone
        if pace:
            self.identity.pace = pace
        if values:
            self.identity.values = values

        self._save()

    def pause(self) -> None:
        """Pause behavioral learning (keeps existing identity)."""
        self.identity.paused = True
        self._save()

    def resume(self) -> None:
        """Resume behavioral learning."""
        self.identity.paused = False
        self._save()

    def clear(self) -> None:
        """Clear identity completely."""
        self.identity = Identity()
        self._save()

    def force_refresh(self) -> None:
        """Force a digest on next check."""
        self.identity.turn_count_at_digest = 0
        self._recent_observation_count = 100  # Trigger high activity

    async def persist_to_global(self) -> None:
        """Merge session learnings into global identity.

        Called on session end to propagate identity improvements.
        """
        self.global_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing global identity
        global_identity = Identity()
        if self.global_path.exists():
            global_identity = self._load_yaml(self.global_path)

        # Merge observations (keep recent N globally)
        merged_obs = global_identity.observations + self.identity.observations
        global_identity.observations = merged_obs[-MAX_OBSERVATIONS_GLOBAL:]

        # Use session prompt if it has higher confidence
        if (self.identity.is_usable() and
            self.identity.confidence > global_identity.confidence):
            global_identity.prompt = self.identity.prompt
            global_identity.confidence = self.identity.confidence
            global_identity.tone = self.identity.tone
            global_identity.pace = self.identity.pace
            global_identity.values = self.identity.values

        # Save global
        data = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "observation_count": len(global_identity.observations),
            "identity": global_identity.to_dict(),
        }

        with open(self.global_path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    def export(self) -> dict[str, Any]:
        """Export identity data for inspection or backup."""
        return {
            "session_path": str(self.session_path),
            "global_path": str(self.global_path),
            "identity": self.identity.to_dict(),
            "observation_count": len(self.identity.observations),
            "is_usable": self.identity.is_usable(),
        }
