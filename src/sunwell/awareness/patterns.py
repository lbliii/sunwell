"""AwarenessPattern - Data model for behavioral self-observations.

Patterns represent observations about agent behavior (not project facts):
- Confidence calibration: "I overstate confidence on refactoring"
- Tool avoidance: "I under-utilize grep_search"
- Error clustering: "I struggle with async patterns"
- Backtrack rate: "Test writing has high undo rate"
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class PatternType(Enum):
    """Types of behavioral patterns that can be extracted."""

    CONFIDENCE = "confidence"
    """Confidence calibration: stated vs actual accuracy."""

    TOOL_AVOIDANCE = "tool_avoidance"
    """Tools with high success rate but low usage frequency."""

    ERROR_CLUSTER = "error_cluster"
    """Task types with elevated failure rates."""

    BACKTRACK = "backtrack"
    """High undo/restore rate for certain file types or tasks."""


@dataclass(frozen=True, slots=True)
class AwarenessPattern:
    """A behavioral self-observation.

    Patterns are first-person observations about how the agent behaves,
    not facts about the project. They're injected into prompts as
    self-correction hints.

    Example:
        >>> pattern = AwarenessPattern(
        ...     pattern_type=PatternType.CONFIDENCE,
        ...     observation="I overstate confidence on refactoring tasks",
        ...     metric=0.20,  # 20% miscalibration
        ...     sample_size=15,
        ...     context="refactoring",
        ... )
        >>> pattern.confidence
        0.8  # High confidence due to 15 samples
    """

    pattern_type: PatternType
    """Type of behavioral pattern."""

    observation: str
    """First-person observation: 'I tend to overstate confidence on...'"""

    metric: float
    """Quantified signal (e.g., 0.2 for 20% miscalibration)."""

    sample_size: int
    """Number of data points this observation is based on."""

    context: str
    """When this applies: 'refactoring tasks', 'test files', etc."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this pattern was last updated."""

    # Decay tracking (similar to Learning)
    activity_day_created: int = 0
    """Activity day when first observed."""

    activity_day_accessed: int = 0
    """Activity day of last access for prompt injection."""

    reinforcement_count: int = 0
    """How many times this pattern has been re-observed."""

    @property
    def id(self) -> str:
        """Content-addressable ID based on type + context.

        Same pattern type + context = same ID (for deduplication).
        """
        data = f"{self.pattern_type.value}:{self.context}"
        return hashlib.blake2b(data.encode(), digest_size=12).hexdigest()

    @property
    def confidence(self) -> float:
        """How confident we are in this pattern (based on sample size).

        - 3 samples: 0.65
        - 5 samples: 0.75
        - 10 samples: 0.95 (max)

        We need at least 3 data points before injecting into prompts.
        """
        return min(0.95, 0.5 + (self.sample_size * 0.05))

    @property
    def is_significant(self) -> bool:
        """Whether this pattern is significant enough to inject.

        Requires:
        - At least 3 samples
        - Metric above threshold (varies by type)
        """
        if self.sample_size < 3:
            return False

        # Type-specific thresholds
        thresholds = {
            PatternType.CONFIDENCE: 0.10,  # 10% miscalibration
            PatternType.TOOL_AVOIDANCE: 0.30,  # 30% underutilization
            PatternType.ERROR_CLUSTER: 0.25,  # 25% failure rate
            PatternType.BACKTRACK: 0.20,  # 20% backtrack rate
        }

        threshold = thresholds.get(self.pattern_type, 0.20)
        return self.metric >= threshold

    def to_prompt_line(self) -> str:
        """Format as a single line for prompt injection.

        Returns first-person observation suitable for system prompt.
        """
        # Add metric context based on type
        metric_suffix = ""
        if self.pattern_type == PatternType.CONFIDENCE:
            metric_suffix = f" (calibrate ~{int(self.metric * 100)}%)"
        elif self.pattern_type == PatternType.TOOL_AVOIDANCE:
            metric_suffix = f" ({int(self.metric * 100)}% success rate when used)"
        elif self.pattern_type == PatternType.ERROR_CLUSTER:
            metric_suffix = f" ({int(self.metric * 100)}% failure rate)"
        elif self.pattern_type == PatternType.BACKTRACK:
            metric_suffix = f" ({int(self.metric * 100)}% backtrack rate)"

        return f"- {self.observation}{metric_suffix}"

    def with_reinforcement(self, new_metric: float, new_samples: int) -> "AwarenessPattern":
        """Create updated pattern with merged observations.

        Args:
            new_metric: Metric from new observation
            new_samples: Sample count from new observation

        Returns:
            New pattern with combined statistics
        """
        # Weighted average of metrics
        total_samples = self.sample_size + new_samples
        combined_metric = (
            (self.metric * self.sample_size) + (new_metric * new_samples)
        ) / total_samples

        return AwarenessPattern(
            pattern_type=self.pattern_type,
            observation=self.observation,
            metric=combined_metric,
            sample_size=total_samples,
            context=self.context,
            timestamp=datetime.now().isoformat(),
            activity_day_created=self.activity_day_created,
            activity_day_accessed=self.activity_day_accessed,
            reinforcement_count=self.reinforcement_count + 1,
        )

    def with_access(self, activity_day: int) -> "AwarenessPattern":
        """Create pattern with updated access tracking.

        Args:
            activity_day: Current cumulative activity day

        Returns:
            New pattern with updated access timestamp
        """
        return AwarenessPattern(
            pattern_type=self.pattern_type,
            observation=self.observation,
            metric=self.metric,
            sample_size=self.sample_size,
            context=self.context,
            timestamp=self.timestamp,
            activity_day_created=self.activity_day_created,
            activity_day_accessed=activity_day,
            reinforcement_count=self.reinforcement_count,
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type.value,
            "observation": self.observation,
            "metric": self.metric,
            "sample_size": self.sample_size,
            "context": self.context,
            "timestamp": self.timestamp,
            "activity_day_created": self.activity_day_created,
            "activity_day_accessed": self.activity_day_accessed,
            "reinforcement_count": self.reinforcement_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AwarenessPattern":
        """Deserialize from dict."""
        return cls(
            pattern_type=PatternType(data["pattern_type"]),
            observation=data["observation"],
            metric=data["metric"],
            sample_size=data["sample_size"],
            context=data["context"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            activity_day_created=data.get("activity_day_created", 0),
            activity_day_accessed=data.get("activity_day_accessed", 0),
            reinforcement_count=data.get("reinforcement_count", 0),
        )


def format_patterns_for_prompt(patterns: list[AwarenessPattern]) -> str:
    """Format multiple patterns for system prompt injection.

    Args:
        patterns: List of patterns to format

    Returns:
        Formatted string for system prompt, or empty string if no patterns
    """
    if not patterns:
        return ""

    # Filter to significant patterns only
    significant = [p for p in patterns if p.is_significant]
    if not significant:
        return ""

    # Sort by confidence (most confident first)
    significant.sort(key=lambda p: p.confidence, reverse=True)

    # Limit to top 5 patterns
    top_patterns = significant[:5]

    lines = ["Based on recent sessions:"]
    for pattern in top_patterns:
        lines.append(pattern.to_prompt_line())

    return "\n".join(lines)
