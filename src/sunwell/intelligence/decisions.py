"""Decision Memory - RFC-045 Phase 1 + RFC-050 Bootstrap Extensions.

Architectural decisions are first-class citizens that persist forever.
Records why we chose X over Y, with rationale and context.

RFC-050 adds:
- source field to track bootstrap vs conversation decisions
- metadata field for provenance tracking
"""


import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sunwell.embedding.protocol import EmbeddingProtocol

# RFC-050: Decision sources
DecisionSource = Literal["conversation", "bootstrap"]


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

    # RFC-050: Bootstrap extensions
    source: DecisionSource = "conversation"
    """Where this decision came from: 'conversation' or 'bootstrap'."""

    metadata: dict[str, Any] | None = None
    """Optional metadata for provenance tracking (source file, commit, etc.)."""

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        result = {
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
            # RFC-050: Bootstrap extensions
            "source": self.source,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result

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
            # RFC-050: Bootstrap extensions
            source=data.get("source", "conversation"),
            metadata=data.get("metadata"),
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
        # RFC-050: Bootstrap extensions
        source: DecisionSource = "conversation",
        metadata: dict[str, Any] | None = None,
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
            source: Where decision came from ('conversation' or 'bootstrap')
            metadata: Optional metadata for provenance tracking

        Returns:
            The recorded Decision

        Bootstrap decisions are marked with:
        - source="bootstrap"
        - Lower confidence (0.6-0.8)
        - No rejected options (not known from commits/docs)

        Bootstrap decisions upgrade to conversation confidence when:
        - User references them without contradiction
        - Explicit confirmation during chat
        """
        decision_id = self._generate_id(category, question, choice)

        # If superseding, mark old decision as superseded
        if supersedes and supersedes in self._decisions:
            # Note: Old decision is kept, new one references it via supersedes link
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
            session_id=session_id if source == "conversation" else "bootstrap",
            supersedes=supersedes,
            source=source,
            metadata=metadata,
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
        source: DecisionSource | None = None,
    ) -> list[Decision]:
        """Get decisions, optionally filtered by category and/or source.

        Args:
            category: Filter by category (None = all)
            active_only: If True, exclude superseded decisions
            source: Filter by source ('conversation', 'bootstrap', or None for all)

        Returns:
            List of decisions
        """
        decisions = list(self._decisions.values())

        if category:
            decisions = [d for d in decisions if d.category == category]

        if source:
            decisions = [d for d in decisions if d.source == source]

        if active_only:
            # Exclude decisions that have been superseded
            superseded_ids = {d.supersedes for d in decisions if d.supersedes}
            decisions = [d for d in decisions if d.id not in superseded_ids]

        # Sort by timestamp (newest first)
        decisions.sort(key=lambda d: d.timestamp, reverse=True)

        return decisions

    async def get_bootstrap_stats(self) -> dict[str, int]:
        """Get statistics about bootstrapped vs conversation decisions.

        Returns:
            Dict with counts: {'bootstrap': N, 'conversation': M, 'total': N+M}
        """
        all_decisions = await self.get_decisions(active_only=True)
        bootstrap_count = sum(1 for d in all_decisions if d.source == "bootstrap")
        conversation_count = sum(1 for d in all_decisions if d.source == "conversation")
        return {
            "bootstrap": bootstrap_count,
            "conversation": conversation_count,
            "total": len(all_decisions),
        }

    async def upgrade_bootstrap_decision(
        self,
        decision_id: str,
        new_confidence: float = 0.90,
        session_id: str = "",
    ) -> Decision | None:
        """Upgrade a bootstrap decision to higher confidence after user confirmation.

        Called when user references or confirms a bootstrap decision without contradiction.

        Args:
            decision_id: ID of the decision to upgrade
            new_confidence: New confidence level (default 0.90)
            session_id: Session where confirmation occurred

        Returns:
            Updated Decision or None if not found
        """
        if decision_id not in self._decisions:
            return None

        old_decision = self._decisions[decision_id]
        if old_decision.source != "bootstrap":
            return old_decision  # Already a conversation decision

        # Create upgraded decision
        upgraded = Decision(
            id=old_decision.id,
            category=old_decision.category,
            question=old_decision.question,
            choice=old_decision.choice,
            rejected=old_decision.rejected,
            rationale=old_decision.rationale,
            context=old_decision.context,
            confidence=new_confidence,
            timestamp=datetime.now(),
            session_id=session_id or old_decision.session_id,
            supersedes=None,
            source="conversation",  # Upgraded to conversation-confirmed
            metadata={
                **(old_decision.metadata or {}),
                "upgraded_from": "bootstrap",
                "original_confidence": old_decision.confidence,
            },
        )

        self._decisions[decision_id] = upgraded
        self._save_decision(upgraded)
        return upgraded

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

            # If proposed choice differs and they seem mutually exclusive
            is_alternative = (
                choice_lower != proposed_lower and
                self._are_mutually_exclusive(choice_lower, proposed_lower)
            )
            if is_alternative:
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
