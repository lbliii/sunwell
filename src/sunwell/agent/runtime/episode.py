"""Episodic snapshots for portable expertise state.

This module enables capturing, saving, and restoring "expertise sessions" -
the complete state of a lens application including what was retrieved,
what was validated, and what refinements were made.

Use cases:
- Resume interrupted work
- Share expertise sessions with colleagues
- Audit trail for compliance
- Reproduce results exactly
- Transfer expertise across machines
"""


import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.execution.manager import ExecutionResult
    from sunwell.foundation.core.lens import Lens


@dataclass(frozen=True, slots=True)
class EpisodeSnapshot:
    """Portable snapshot of an expertise application session.

    Captures everything needed to understand and reproduce what
    Sunwell did during a lens application:

    - What expertise was retrieved (heuristics, personas, validators)
    - What code context was used
    - How the output was validated
    - What refinements were made

    This enables:
    - **Resumability**: Continue where you left off
    - **Portability**: Share sessions across machines
    - **Auditability**: Full trace of AI assistance
    - **Reproducibility**: Re-run with same expertise
    """

    # Identity
    lens_name: str
    lens_version: str
    lens_domain: str

    # Input
    prompt: str

    # Retrieved expertise (tuples for immutability in frozen dataclass)
    retrieved_heuristics: tuple[str, ...] = ()
    retrieved_code: tuple[str, ...] = ()

    # Execution
    tier: str = "STANDARD"
    refinement_count: int = 0

    # Validation results (tuples for immutability in frozen dataclass)
    validation_results: tuple[dict, ...] = ()
    persona_results: tuple[dict, ...] = ()

    # Output
    final_content: str = ""
    confidence_score: float = 0.0
    confidence_level: str = "unknown"

    # Metadata
    timestamp: str = ""
    duration_ms: float = 0.0
    model: str = ""
    token_usage: tuple[tuple[str, int], ...] = ()

    @classmethod
    def from_result(
        cls,
        lens: Lens,
        prompt: str,
        result: ExecutionResult,
        retrieved_code: list[str] | None = None,
        model: str = "",
        duration_ms: float = 0.0,
    ) -> EpisodeSnapshot:
        """Create snapshot from execution result."""
        return cls(
            # Lens info
            lens_name=lens.metadata.name,
            lens_version=str(lens.metadata.version),
            lens_domain=lens.metadata.domain,

            # Input
            prompt=prompt,

            # Retrieved (tuples for frozen dataclass)
            retrieved_heuristics=tuple(result.retrieved_components),
            retrieved_code=tuple(retrieved_code) if retrieved_code else (),

            # Execution
            tier=result.tier.name,
            refinement_count=result.refinement_count,

            # Validation (tuples for frozen dataclass)
            validation_results=tuple(
                {
                    "name": v.validator_name,
                    "passed": v.passed,
                    "message": v.message,
                    "confidence": v.confidence,
                }
                for v in result.validation_results
            ),
            persona_results=tuple(
                {
                    "name": p.persona_name,
                    "approved": p.approved,
                    "feedback": p.feedback[:500] if p.feedback else None,
                }
                for p in result.persona_results
            ),

            # Output
            final_content=result.content,
            confidence_score=result.confidence.score,
            confidence_level=result.confidence.level,

            # Metadata
            timestamp=datetime.now().isoformat(),
            model=model,
            duration_ms=duration_ms,
            token_usage=(
                ("prompt", result.token_usage.prompt_tokens if result.token_usage else 0),
                ("completion", result.token_usage.completion_tokens if result.token_usage else 0),
            ),
        )

    def save(self, path: Path) -> None:
        """Save snapshot to JSON file.

        Uses Zstandard compression for large snapshots (Python 3.14).
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)

        # Use compression for large content
        if len(self.final_content) > 10000:
            try:
                import zstd
                compressed = zstd.compress(self.final_content.encode())
                data["final_content_compressed"] = compressed.hex()
                data["final_content"] = "[compressed]"
            except ImportError:
                pass  # Fall back to uncompressed

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> EpisodeSnapshot:
        """Load snapshot from JSON file."""
        with open(path) as f:
            data = json.load(f)

        # Decompress if needed
        if data.get("final_content") == "[compressed]" and "final_content_compressed" in data:
            try:
                import zstd
                compressed = bytes.fromhex(data["final_content_compressed"])
                data["final_content"] = zstd.decompress(compressed).decode()
            except ImportError:
                data["final_content"] = "[compression library not available]"
            del data["final_content_compressed"]

        # Convert lists to tuples for frozen dataclass
        data["retrieved_heuristics"] = tuple(data.get("retrieved_heuristics", ()))
        data["retrieved_code"] = tuple(data.get("retrieved_code", ()))
        data["validation_results"] = tuple(data.get("validation_results", ()))
        data["persona_results"] = tuple(data.get("persona_results", ()))
        # Convert token_usage dict to tuple of tuples
        token_usage = data.get("token_usage", {})
        if isinstance(token_usage, dict):
            data["token_usage"] = tuple(token_usage.items())

        return cls(**data)

    def summary(self) -> str:
        """Human-readable summary of the session."""
        passed = sum(1 for v in self.validation_results if v.get("passed"))
        total = len(self.validation_results)

        return f"""Episode: {self.lens_name} v{self.lens_version}
Timestamp: {self.timestamp}
Tier: {self.tier}
Confidence: {self.confidence_score:.0%} ({self.confidence_level})
Validations: {passed}/{total} passed
Refinements: {self.refinement_count}
Heuristics: {', '.join(self.retrieved_heuristics) or 'none'}
Code refs: {len(self.retrieved_code)} files"""


@dataclass(slots=True)
class EpisodeChain:
    """Chain of related episodes for multi-step workflows.

    Enables tracking expertise application across a series
    of related tasks - like a git history for AI assistance.
    """

    episodes: list[EpisodeSnapshot] = field(default_factory=list)

    def add(self, episode: EpisodeSnapshot) -> None:
        """Add an episode to the chain."""
        self.episodes.append(episode)

    def save(self, path: Path) -> None:
        """Save chain to JSON file."""
        data = {"episodes": [asdict(e) for e in self.episodes]}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> EpisodeChain:
        """Load chain from JSON file."""
        with open(path) as f:
            data = json.load(f)
        # Use EpisodeSnapshot.load logic for each episode to handle tuple conversion
        episodes = []
        for e in data["episodes"]:
            e["retrieved_heuristics"] = tuple(e.get("retrieved_heuristics", ()))
            e["retrieved_code"] = tuple(e.get("retrieved_code", ()))
            e["validation_results"] = tuple(e.get("validation_results", ()))
            e["persona_results"] = tuple(e.get("persona_results", ()))
            token_usage = e.get("token_usage", {})
            if isinstance(token_usage, dict):
                e["token_usage"] = tuple(token_usage.items())
            episodes.append(EpisodeSnapshot(**e))
        return cls(episodes=episodes)

    @property
    def latest(self) -> EpisodeSnapshot | None:
        """Most recent episode."""
        return self.episodes[-1] if self.episodes else None

    def rollback(self, n: int = 1) -> EpisodeSnapshot | None:
        """Get episode from n steps back."""
        if n <= len(self.episodes):
            return self.episodes[-n]
        return None
