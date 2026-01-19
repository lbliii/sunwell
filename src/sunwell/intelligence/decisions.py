"""Decision Memory - RFC-045 Phase 1.

Architectural decisions are first-class citizens that persist forever.
Records why we chose X over Y, with rationale and context.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.embedding.protocol import EmbeddingProtocol


@dataclass(frozen=True, slots=True)
class RejectedOption:
    """An option that was considered but rejected."""

    option: str
    """What was rejected: 'Redis caching'."""

    reason: str
    """Why it was rejected: 'Too much operational complexity for our scale'."""

    might_reconsider_when: str | None = None
    """Conditions that might change this: 'If we need sub-ms latency'."""


@dataclass(frozen=True, slots=True)
class Decision:
    """An architectural decision that persists across sessions."""

    id: str
    """Unique identifier (hash of context + choice)."""

    category: str
    """Category: 'database', 'auth', 'framework', 'pattern', etc."""

    question: str
    """What decision was being made: 'Which database to use?'"""

    choice: str
    """What was chosen: 'SQLAlchemy with SQLite'."""

    rejected: tuple[RejectedOption, ...]
    """Options that were considered but rejected."""

    rationale: str
    """Why this choice was made."""

    context: str
    """Project context when decision was made."""

    confidence: float
    """How confident we are this is still the right choice (0.0-1.0)."""

    timestamp: datetime
    """When decision was made."""

    session_id: str
    """Which session this came from."""

    supersedes: str | None = None
    """ID of decision this replaces (if changed)."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "id": self.id,
            "category": self.category,
            "question": self.question,
            "choice": self.choice,
            "rejected": [
                {
                    "option": r.option,
                    "reason": r.reason,
                    "might_reconsider_when": r.might_reconsider_when,
                }
                for r in self.rejected
            ],
            "rationale": self.rationale,
            "context": self.context,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "supersedes": self.supersedes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Decision:
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            category=data["category"],
            question=data["question"],
            choice=data["choice"],
            rejected=tuple(
                RejectedOption(
                    option=r["option"],
                    reason=r["reason"],
                    might_reconsider_when=r.get("might_reconsider_when"),
                )
                for r in data["rejected"]
            ),
            rationale=data["rationale"],
            context=data["context"],
            confidence=data["confidence"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data["session_id"],
            supersedes=data.get("supersedes"),
        )

    def to_text(self) -> str:
        """Convert to text for embedding/search."""
        parts = [
            f"Category: {self.category}",
            f"Question: {self.question}",
            f"Choice: {self.choice}",
            f"Rationale: {self.rationale}",
        ]
        if self.rejected:
            parts.append("Rejected options:")
            for r in self.rejected:
                parts.append(f"  - {r.option}: {r.reason}")
        return "\n".join(parts)


class DecisionMemory:
    """Manages architectural decisions across sessions.

    Storage: `.sunwell/intelligence/decisions.jsonl` (append-only)
    """

    def __init__(
        self,
        base_path: Path,
        embedder: EmbeddingProtocol | None = None,
    ):
        """Initialize decision memory.

        Args:
            base_path: Base path for intelligence storage (.sunwell/intelligence)
            embedder: Optional embedder for semantic search
        """
        self.base_path = Path(base_path)
        self.decisions_path = self.base_path / "decisions.jsonl"
        self.embeddings_path = self.base_path / "decisions_embeddings.json"
        self._embedder = embedder

        # In-memory cache
        self._decisions: dict[str, Decision] = {}
        self._embeddings: dict[str, list[float]] = {}

        # Ensure directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Load existing decisions
        self._load_decisions()

    def _load_decisions(self) -> None:
        """Load decisions from JSONL file."""
        if not self.decisions_path.exists():
            return

        with open(self.decisions_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    decision = Decision.from_dict(data)
                    self._decisions[decision.id] = decision
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        # Load embeddings if available
        if self.embeddings_path.exists():
            try:
                with open(self.embeddings_path) as f:
                    self._embeddings = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._embeddings = {}

    def _save_decision(self, decision: Decision) -> None:
        """Append decision to JSONL file."""
        with open(self.decisions_path, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    def _save_embeddings(self) -> None:
        """Save embeddings to JSON file."""
        with open(self.embeddings_path, "w") as f:
            json.dump(self._embeddings, f)

    def _generate_id(
        self,
        category: str,
        question: str,
        choice: str,
    ) -> str:
        """Generate unique ID for decision."""
        content = f"{category}:{question}:{choice}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def record_decision(
        self,
        category: str,
        question: str,
        choice: str,
        rejected: list[tuple[str, str]],
        rationale: str,
        context: str = "",
        session_id: str = "",
        confidence: float = 1.0,
        supersedes: str | None = None,
    ) -> Decision:
        """Record a new architectural decision.

        Args:
            category: Decision category (e.g., 'database', 'auth')
            question: What decision was being made
            choice: What was chosen
            rejected: List of (option, reason) tuples for rejected options
            rationale: Why this choice was made
            context: Project context when decision was made
            session_id: Session identifier
            confidence: Confidence level (0.0-1.0)
            supersedes: ID of decision this replaces (if changed)

        Returns:
            The recorded Decision
        """
        decision_id = self._generate_id(category, question, choice)

        # If superseding, mark old decision as superseded
        if supersedes and supersedes in self._decisions:
            # Update existing decision (create new one with supersedes link)
            old_decision = self._decisions[supersedes]
            # Keep old decision but create new one
            pass

        rejected_options = tuple(
            RejectedOption(option=opt, reason=reason)
            for opt, reason in rejected
        )

        decision = Decision(
            id=decision_id,
            category=category,
            question=question,
            choice=choice,
            rejected=rejected_options,
            rationale=rationale,
            context=context,
            confidence=confidence,
            timestamp=datetime.now(),
            session_id=session_id,
            supersedes=supersedes,
        )

        self._decisions[decision.id] = decision
        self._save_decision(decision)

        # Generate embedding if embedder available
        if self._embedder:
            try:
                text = decision.to_text()
                result = await self._embedder.embed([text])
                self._embeddings[decision.id] = result.vectors[0].tolist()
                self._save_embeddings()
            except Exception:
                # Embedding generation is optional
                pass

        return decision

    async def get_decisions(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[Decision]:
        """Get decisions, optionally filtered by category.

        Args:
            category: Filter by category (None = all)
            active_only: If True, exclude superseded decisions

        Returns:
            List of decisions
        """
        decisions = list(self._decisions.values())

        if category:
            decisions = [d for d in decisions if d.category == category]

        if active_only:
            # Exclude decisions that have been superseded
            superseded_ids = {d.supersedes for d in decisions if d.supersedes}
            decisions = [d for d in decisions if d.id not in superseded_ids]

        # Sort by timestamp (newest first)
        decisions.sort(key=lambda d: d.timestamp, reverse=True)

        return decisions

    async def find_relevant_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[Decision]:
        """Find decisions relevant to a query using embeddings.

        Args:
            query: Natural language query
            top_k: Maximum number of decisions to return

        Returns:
            List of relevant decisions sorted by relevance
        """
        if not self._embedder or not self._embeddings:
            # Fall back to keyword search
            return self._keyword_search(query, top_k)

        try:
            # Embed query
            result = await self._embedder.embed([query])
            query_vec = result.vectors[0].tolist()

            # Calculate similarities
            scores: list[tuple[Decision, float]] = []
            for decision_id, decision_embedding in self._embeddings.items():
                if decision_id not in self._decisions:
                    continue

                decision = self._decisions[decision_id]

                # Skip superseded decisions
                if decision.supersedes:
                    continue

                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_vec, decision_embedding)
                scores.append((decision, similarity))

            # Sort by score and return top_k
            scores.sort(key=lambda x: x[1], reverse=True)
            return [d for d, _ in scores[:top_k]]

        except Exception:
            # Fall back to keyword search on error
            return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> list[Decision]:
        """Fallback keyword search when embeddings unavailable."""
        query_lower = query.lower()
        scores: list[tuple[Decision, int]] = []

        for decision in self._decisions.values():
            if decision.supersedes:
                continue

            score = 0
            text = decision.to_text().lower()

            # Count keyword matches
            for word in query_lower.split():
                if word in text:
                    score += 1

            if score > 0:
                scores.append((decision, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [d for d, _ in scores[:top_k]]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot = sum(x * y for x, y in zip(a, b, strict=True))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    async def check_contradiction(
        self,
        proposed_choice: str,
        category: str,
    ) -> Decision | None:
        """Check if proposed choice contradicts an existing decision.

        Args:
            proposed_choice: The proposed choice
            category: Decision category

        Returns:
            Contradicting decision if found, None otherwise
        """
        # Get relevant decisions in this category
        decisions = await self.get_decisions(category=category, active_only=True)

        # Simple keyword-based contradiction detection
        proposed_lower = proposed_choice.lower()

        for decision in decisions:
            # Check if choice contradicts
            choice_lower = decision.choice.lower()

            # If proposed choice mentions something that was rejected
            for rejected in decision.rejected:
                rejected_lower = rejected.option.lower()
                if rejected_lower in proposed_lower:
                    return decision

            # If proposed choice is different from existing choice
            # and they seem to be alternatives
            if choice_lower != proposed_lower:
                # Check if they're mutually exclusive (simple heuristic)
                if self._are_mutually_exclusive(choice_lower, proposed_lower):
                    return decision

        return None

    def _are_mutually_exclusive(self, choice1: str, choice2: str) -> bool:
        """Heuristic to detect if two choices are mutually exclusive."""
        # Simple patterns for common mutually exclusive choices
        patterns = [
            ("sqlite", "postgres"),
            ("postgres", "sqlite"),
            ("jwt", "oauth"),
            ("oauth", "jwt"),
            ("redis", "in-memory"),
            ("in-memory", "redis"),
            ("sync", "async"),
            ("async", "sync"),
        ]

        for p1, p2 in patterns:
            if p1 in choice1.lower() and p2 in choice2.lower():
                return True
            if p2 in choice1.lower() and p1 in choice2.lower():
                return True

        return False
