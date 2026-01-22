"""Focus - Attention mechanism for memory retrieval.

Focus replaces vectors with a simpler, more interpretable approach:
1. Extract topics/tags from user query
2. Filter memories by matching tags
3. Include full text (no embedding loss)
4. Let the LLM do the fine-grained relevance

Benefits over vectors:
- No embedding model dependency
- Interpretable (you can see why something was retrieved)
- Full fidelity (text not compressed to vector)
- Simpler (tag matching vs. ANN search)
- Editable (user can adjust focus manually)
"""


import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.simulacrum.core.turn import Learning, Turn


# Common topic patterns for auto-detection
TOPIC_PATTERNS = {
    # Technical domains
    "auth": r"\b(auth|login|logout|session|token|jwt|oauth|password|credential|permission|role)\b",
    "api": r"\b(api|endpoint|request|response|rest|graphql|http|status|route)\b",
    "database": r"\b(database|db|sql|query|table|index|postgres|mysql|mongo|redis)\b",
    "cache": r"\b(cache|redis|memcache|ttl|expire|invalidat)\b",
    "network": r"\b(network|socket|tcp|udp|dns|proxy|firewall|timeout|connection)\b",
    "error": r"\b(error|exception|fail|crash|bug|issue|problem|broken)\b",
    "performance": r"\b(performance|slow|fast|latency|throughput|optimize|bottleneck)\b",
    "security": r"\b(security|vulnerab|inject|xss|csrf|encrypt|decrypt|hash)\b",
    "config": r"\b(config|setting|environment|env|variable|parameter|option)\b",
    "deploy": r"\b(deploy|release|ci|cd|pipeline|docker|kubernetes|container)\b",

    # Actions
    "debug": r"\b(debug|trace|log|inspect|investigate|diagnose)\b",
    "refactor": r"\b(refactor|restructure|reorganize|clean|simplify)\b",
    "test": r"\b(test|spec|assert|mock|fixture|coverage)\b",
    "document": r"\b(document|doc|readme|comment|explain)\b",
}


@dataclass
class Focus:
    """Current attention focus for memory retrieval.

    Focus can be:
    - Explicit: User says "/focus auth"
    - Implicit: Auto-detected from query
    - Persistent: Carries across turns until changed
    - Weighted: Multiple topics with relevance scores
    """

    topics: dict[str, float] = field(default_factory=dict)
    """Topic → weight mapping. Higher = more relevant."""

    explicit: set[str] = field(default_factory=set)
    """Topics explicitly set by user (don't auto-decay)."""

    file_patterns: list[str] = field(default_factory=list)
    """File path patterns to focus on (e.g., "src/auth/*")."""

    decay_rate: float = 0.8
    """How fast implicit topics decay each turn (0-1)."""

    min_weight: float = 0.3
    """Minimum weight to keep a topic active."""

    def update_from_query(self, query: str) -> dict[str, float]:
        """Update focus based on a new query.

        Returns dict of newly detected topics.
        """
        # Decay existing implicit topics
        for topic in list(self.topics.keys()):
            if topic not in self.explicit:
                self.topics[topic] *= self.decay_rate
                if self.topics[topic] < self.min_weight:
                    del self.topics[topic]

        # Detect new topics
        new_topics = {}
        query_lower = query.lower()

        for topic, pattern in TOPIC_PATTERNS.items():
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            if matches:
                weight = min(1.0, 0.5 + 0.1 * len(matches))  # More matches = higher weight

                if topic in self.topics:
                    # Boost existing topic
                    self.topics[topic] = min(1.0, self.topics[topic] + weight)
                else:
                    # Add new topic
                    self.topics[topic] = weight
                    new_topics[topic] = weight

        # Detect file paths mentioned
        file_matches = re.findall(r'[\w/]+\.(py|ts|js|go|rs|java|rb|md|yaml|json)', query)
        for f in file_matches:
            pattern = f"*{f}*"
            if pattern not in self.file_patterns:
                self.file_patterns.append(pattern)

        return new_topics

    def set_explicit(self, topic: str, weight: float = 1.0) -> None:
        """Explicitly set focus on a topic (won't decay)."""
        self.topics[topic] = weight
        self.explicit.add(topic)

    def clear_explicit(self, topic: str) -> None:
        """Remove explicit focus on a topic."""
        self.explicit.discard(topic)
        # Will now decay naturally

    def clear_all(self) -> None:
        """Clear all focus."""
        self.topics.clear()
        self.explicit.clear()
        self.file_patterns.clear()

    @property
    def active_topics(self) -> list[str]:
        """Get topics sorted by weight (highest first)."""
        return sorted(self.topics.keys(), key=lambda t: self.topics[t], reverse=True)

    @property
    def primary_topic(self) -> str | None:
        """Get the highest-weighted topic."""
        if not self.topics:
            return None
        return max(self.topics.keys(), key=lambda t: self.topics[t])

    def matches(self, tags: set[str]) -> float:
        """Score how well a set of tags matches current focus.

        Returns 0-1 relevance score.
        """
        if not self.topics:
            return 0.5  # No focus = neutral relevance

        if not tags:
            return 0.3  # No tags = low relevance

        # Sum weights of matching topics
        total_weight = sum(self.topics.values())
        matching_weight = sum(
            self.topics.get(tag, 0)
            for tag in tags
        )

        if total_weight == 0:
            return 0.5

        return matching_weight / total_weight

    def to_prompt_hint(self) -> str:
        """Format focus as a hint for the LLM."""
        if not self.topics:
            return ""

        parts = ["Current focus:"]
        for topic in self.active_topics[:5]:
            weight = self.topics[topic]
            indicator = "●" if topic in self.explicit else "○"
            parts.append(f"  {indicator} {topic} ({weight:.0%})")

        return "\n".join(parts)


@dataclass
class FocusFilter:
    """Filter memories based on focus."""

    focus: Focus

    def filter_learnings(
        self,
        learnings: list[Learning],
        min_relevance: float = 0.3,
    ) -> list[tuple[Learning, float]]:
        """Filter and score learnings by focus relevance.

        Returns list of (learning, score) tuples, sorted by score.
        """
        scored = []

        for learning in learnings:
            # Extract tags from learning text
            tags = self._extract_tags(learning.fact)

            # Score against focus
            score = self.focus.matches(tags)

            # Category boost
            if learning.category == "dead_end":
                score *= 1.2  # Always want to see dead ends
            elif learning.category == "constraint":
                score *= 1.1  # Constraints are important

            if score >= min_relevance:
                scored.append((learning, score))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    def filter_turns(
        self,
        turns: list[Turn],
        min_relevance: float = 0.3,
    ) -> list[tuple[Turn, float]]:
        """Filter and score turns by focus relevance."""
        scored = []

        for turn in turns:
            tags = self._extract_tags(turn.content)
            score = self.focus.matches(tags)

            if score >= min_relevance:
                scored.append((turn, score))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _extract_tags(self, text: str) -> set[str]:
        """Extract topic tags from text."""
        tags = set()
        text_lower = text.lower()

        for topic, pattern in TOPIC_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                tags.add(topic)

        return tags


def detect_focus_shift(
    old_focus: Focus,
    new_query: str,
) -> tuple[bool, str]:
    """Detect if a query represents a significant focus shift.

    Returns (is_shift, reason).
    """
    # Create temp focus to see what new query would add
    temp = Focus(
        topics=dict(old_focus.topics),
        explicit=set(old_focus.explicit),
    )
    new_topics = temp.update_from_query(new_query)

    if not new_topics:
        return False, ""

    # Check if new topics are very different from old
    old_primary = old_focus.primary_topic
    new_primary = temp.primary_topic

    if old_primary and new_primary and old_primary != new_primary:
        # Primary topic changed
        old_weight = old_focus.topics.get(new_primary, 0)
        new_weight = temp.topics.get(new_primary, 0)

        if new_weight - old_weight > 0.5:
            return True, f"Focus shifting from {old_primary} to {new_primary}"

    return False, ""
