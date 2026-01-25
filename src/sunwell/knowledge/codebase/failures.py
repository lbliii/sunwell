"""Failure Memory - RFC-045 Phase 4.

Remember what didn't work and why. Prevents repeating the same mistakes.
"""


import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


@dataclass(frozen=True, slots=True)
class FailedApproach:
    """An approach that was tried and failed."""

    id: str
    """Unique identifier."""

    description: str
    """What was attempted: 'Async SQLAlchemy with connection pooling'"""

    error_type: str
    """Type of failure: 'runtime_error', 'test_failure', 'user_rejection', 'timeout'"""

    error_message: str
    """Actual error or rejection reason."""

    context: str
    """What we were trying to achieve."""

    code_snapshot: str | None = None
    """The code that failed (if applicable)."""

    fix_attempted: str | None = None
    """What fix was tried (if any)."""

    root_cause: str | None = None
    """Root cause analysis (if determined)."""

    similar_to: tuple[str, ...] = ()
    """IDs of similar past failures (pattern detection)."""

    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "description": self.description,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "context": self.context,
            "code_snapshot": self.code_snapshot,
            "fix_attempted": self.fix_attempted,
            "root_cause": self.root_cause,
            "similar_to": list(self.similar_to),
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FailedApproach:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            error_type=data["error_type"],
            error_message=data["error_message"],
            context=data["context"],
            code_snapshot=data.get("code_snapshot"),
            fix_attempted=data.get("fix_attempted"),
            root_cause=data.get("root_cause"),
            similar_to=tuple(data.get("similar_to", [])),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id", ""),
        )

    def to_text(self) -> str:
        """Convert to text for embedding/search."""
        parts = [
            f"Description: {self.description}",
            f"Error: {self.error_type} - {self.error_message}",
            f"Context: {self.context}",
        ]
        if self.root_cause:
            parts.append(f"Root cause: {self.root_cause}")
        return "\n".join(parts)


class FailureMemory:
    """Tracks failed approaches to avoid repeating mistakes.

    Storage: `.sunwell/intelligence/failures.jsonl` (append-only)
    """

    def __init__(
        self,
        base_path: Path,
        embedder: EmbeddingProtocol | None = None,
    ):
        """Initialize failure memory.

        Args:
            base_path: Base path for intelligence storage (.sunwell/intelligence)
            embedder: Optional embedder for semantic search
        """
        self.base_path = Path(base_path)
        self.failures_path = self.base_path / "failures.jsonl"
        self.embeddings_path = self.base_path / "failures_embeddings.json"
        self._embedder = embedder

        # In-memory cache
        self._failures: dict[str, FailedApproach] = {}
        self._embeddings: dict[str, list[float]] = {}

        # Ensure directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Load existing failures
        self._load_failures()

    def _load_failures(self) -> None:
        """Load failures from JSONL file."""
        if not self.failures_path.exists():
            return

        with open(self.failures_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    failure = FailedApproach.from_dict(data)
                    self._failures[failure.id] = failure
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        # Load embeddings if available
        if self.embeddings_path.exists():
            try:
                with open(self.embeddings_path) as f:
                    self._embeddings = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._embeddings = {}

    def _save_failure(self, failure: FailedApproach) -> None:
        """Append failure to JSONL file."""
        with open(self.failures_path, "a") as f:
            f.write(json.dumps(failure.to_dict()) + "\n")

    def _save_embeddings(self) -> None:
        """Save embeddings to JSON file."""
        with open(self.embeddings_path, "w") as f:
            json.dump(self._embeddings, f)

    def _generate_id(self, description: str, error_message: str) -> str:
        """Generate unique ID for failure."""
        content = f"{description}:{error_message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def record_failure(
        self,
        description: str,
        error_type: str,
        error_message: str,
        context: str,
        code: str | None = None,
        fix_attempted: str | None = None,
        root_cause: str | None = None,
        session_id: str = "",
    ) -> FailedApproach:
        """Record a failed approach.

        Args:
            description: What was attempted
            error_type: Type of failure
            error_message: Actual error or rejection reason
            context: What we were trying to achieve
            code: The code that failed (if applicable)
            fix_attempted: What fix was tried (if any)
            root_cause: Root cause analysis (if determined)
            session_id: Session identifier

        Returns:
            The recorded FailedApproach
        """
        failure_id = self._generate_id(description, error_message)

        # Check for similar failures
        similar_ids = await self._find_similar_ids(description, error_message)

        failure = FailedApproach(
            id=failure_id,
            description=description,
            error_type=error_type,
            error_message=error_message,
            context=context,
            code_snapshot=code,
            fix_attempted=fix_attempted,
            root_cause=root_cause,
            similar_to=tuple(similar_ids),
            session_id=session_id,
        )

        self._failures[failure.id] = failure
        self._save_failure(failure)

        # Generate embedding if embedder available
        if self._embedder:
            try:
                text = failure.to_text()
                result = await self._embedder.embed([text])
                self._embeddings[failure.id] = result.vectors[0].tolist()
                self._save_embeddings()
            except Exception:
                # Embedding generation is optional
                pass

        return failure

    async def _find_similar_ids(
        self,
        description: str,
        error_message: str,
    ) -> list[str]:
        """Find IDs of similar past failures."""
        if not self._embedder or not self._embeddings:
            return []

        try:
            query_text = f"{description} {error_message}"
            result = await self._embedder.embed([query_text])
            query_vec = result.vectors[0].tolist()

            scores: list[tuple[str, float]] = []
            for failure_id, failure_embedding in self._embeddings.items():
                similarity = _cosine_similarity(query_vec, failure_embedding)
                if similarity > 0.7:  # Threshold for similarity
                    scores.append((failure_id, similarity))

            # Sort by score and return top 3
            scores.sort(key=lambda x: x[1], reverse=True)
            return [fid for fid, _ in scores[:3]]

        except Exception:
            return []

    async def check_similar_failures(
        self,
        proposed_approach: str,
        top_k: int = 3,
    ) -> list[FailedApproach]:
        """Check if proposed approach is similar to past failures.

        Args:
            proposed_approach: Description of proposed approach
            top_k: Maximum number of similar failures to return

        Returns:
            List of similar failures sorted by similarity
        """
        if not self._embedder or not self._embeddings:
            # Fall back to keyword search
            return self._keyword_search(proposed_approach, top_k)

        try:
            # Embed query
            result = await self._embedder.embed([proposed_approach])
            query_vec = result.vectors[0].tolist()

            # Calculate similarities
            scores: list[tuple[FailedApproach, float]] = []
            for failure_id, failure_embedding in self._embeddings.items():
                if failure_id not in self._failures:
                    continue

                failure = self._failures[failure_id]

                # Calculate cosine similarity
                similarity = _cosine_similarity(query_vec, failure_embedding)
                if similarity > 0.6:  # Threshold
                    scores.append((failure, similarity))

            # Sort by score and return top_k
            scores.sort(key=lambda x: x[1], reverse=True)
            return [f for f, _ in scores[:top_k]]

        except Exception:
            # Fall back to keyword search on error
            return self._keyword_search(proposed_approach, top_k)

    def _keyword_search(self, query: str, top_k: int) -> list[FailedApproach]:
        """Fallback keyword search when embeddings unavailable."""
        query_lower = query.lower()
        scores: list[tuple[FailedApproach, int]] = []

        for failure in self._failures.values():
            score = 0
            text = failure.to_text().lower()

            # Count keyword matches
            for word in query_lower.split():
                if word in text:
                    score += 1

            if score > 0:
                scores.append((failure, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in scores[:top_k]]

    async def get_failure_patterns(self) -> list[dict]:
        """Identify recurring failure patterns.

        Returns:
            List of patterns with counts and examples
        """
        # Group failures by error type and description similarity
        patterns: dict[str, list[FailedApproach]] = {}

        for failure in self._failures.values():
            key = f"{failure.error_type}:{failure.description[:50]}"
            if key not in patterns:
                patterns[key] = []
            patterns[key].append(failure)

        # Filter patterns with multiple occurrences
        recurring = [
            {
                "pattern": key,
                "count": len(failures),
                "examples": [f.description for f in failures[:3]],
                "error_type": failures[0].error_type,
            }
            for key, failures in patterns.items()
            if len(failures) > 1
        ]

        # Sort by count (most frequent first)
        recurring.sort(key=lambda x: x["count"], reverse=True)

        return recurring
