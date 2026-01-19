"""Metadata classes for simulacrum management.

RFC-025: Extracted from manager.py to slim it down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArchiveMetadata:
    """Metadata for an archived simulacrum."""

    name: str
    description: str
    domains: tuple[str, ...]
    archived_at: str
    original_created_at: str
    last_accessed: str
    node_count: int
    learning_count: int
    archive_reason: str  # "stale", "manual", "merged", "empty"
    archive_path: str  # Path to archived data

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "domains": list(self.domains),
            "archived_at": self.archived_at,
            "original_created_at": self.original_created_at,
            "last_accessed": self.last_accessed,
            "node_count": self.node_count,
            "learning_count": self.learning_count,
            "archive_reason": self.archive_reason,
            "archive_path": self.archive_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ArchiveMetadata:
        return cls(
            name=data["name"],
            description=data["description"],
            domains=tuple(data.get("domains", [])),
            archived_at=data["archived_at"],
            original_created_at=data["original_created_at"],
            last_accessed=data["last_accessed"],
            node_count=data.get("node_count", 0),
            learning_count=data.get("learning_count", 0),
            archive_reason=data.get("archive_reason", "unknown"),
            archive_path=data.get("archive_path", ""),
        )


@dataclass
class SimulacrumMetadata:
    """Metadata about a simulacrum for routing and display."""

    name: str
    """Unique identifier for the simulacrum."""

    description: str
    """What this simulacrum is for."""

    domains: tuple[str, ...] = ()
    """Domain tags for routing (e.g., "security", "api", "docs")."""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0

    # Stats
    node_count: int = 0
    learning_count: int = 0

    # Auto-spawning metadata
    auto_spawned: bool = False
    """Whether this simulacrum was auto-created."""

    spawn_trigger_queries: tuple[str, ...] = ()
    """Queries that triggered the spawn (for context)."""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "domains": list(self.domains),
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "node_count": self.node_count,
            "learning_count": self.learning_count,
            "auto_spawned": self.auto_spawned,
            "spawn_trigger_queries": list(self.spawn_trigger_queries),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SimulacrumMetadata:
        return cls(
            name=data["name"],
            description=data["description"],
            domains=tuple(data.get("domains", [])),
            created_at=data.get("created_at", ""),
            last_accessed=data.get("last_accessed", ""),
            access_count=data.get("access_count", 0),
            node_count=data.get("node_count", 0),
            learning_count=data.get("learning_count", 0),
            auto_spawned=data.get("auto_spawned", False),
            spawn_trigger_queries=tuple(data.get("spawn_trigger_queries", [])),
        )


@dataclass
class PendingDomain:
    """Tracks queries that might form a new simulacrum."""

    queries: list[str] = field(default_factory=list)
    """Accumulated queries in this potential domain."""

    keywords: dict[str, int] = field(default_factory=dict)
    """Keyword frequency from queries."""

    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this domain was first detected."""

    def add_query(self, query: str) -> None:
        """Add a query and extract keywords."""
        self.queries.append(query)

        # Extract keywords (simple tokenization)
        words = query.lower().split()
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "must", "shall",
                      "can", "need", "dare", "ought", "used", "to", "of", "in",
                      "for", "on", "with", "at", "by", "from", "as", "into", "like",
                      "through", "after", "over", "between", "out", "against",
                      "during", "without", "before", "under", "around", "among",
                      "i", "you", "he", "she", "it", "we", "they", "what", "which",
                      "who", "when", "where", "why", "how", "all", "each", "every",
                      "both", "few", "more", "most", "other", "some", "such", "no",
                      "nor", "not", "only", "own", "same", "so", "than", "too",
                      "very", "just", "my", "your", "his", "her", "its", "our"}

        for word in words:
            # Clean punctuation
            word = word.strip(".,!?;:\"'()[]{}").lower()
            if len(word) > 2 and word not in stop_words:
                self.keywords[word] = self.keywords.get(word, 0) + 1

    def top_keywords(self, n: int = 5) -> list[str]:
        """Get top N keywords by frequency."""
        sorted_kw = sorted(self.keywords.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in sorted_kw[:n]]

    def coherence_score(self) -> float:
        """Estimate how coherent this domain is (0-1).

        Higher = queries are about related topics.
        """
        if len(self.queries) < 2:
            return 0.0

        # Calculate keyword concentration
        # If a few keywords dominate, the domain is coherent
        total_mentions = sum(self.keywords.values())
        if total_mentions == 0:
            return 0.0

        top_5_mentions = sum(c for _, c in sorted(
            self.keywords.items(), key=lambda x: x[1], reverse=True
        )[:5])

        return min(top_5_mentions / total_mentions, 1.0)
