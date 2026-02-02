"""AwarenessStore - Persist and retrieve behavioral patterns.

Stores patterns in `.sunwell/awareness/patterns.jsonl`, handles:
- Deduplication by pattern_type + context
- Decay of stale patterns
- Retrieval of significant patterns for prompt injection
"""

import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from sunwell.awareness.patterns import AwarenessPattern, PatternType

logger = logging.getLogger(__name__)

# Default storage location
DEFAULT_AWARENESS_DIR = Path(".sunwell/awareness")
PATTERNS_FILE = "patterns.jsonl"

# Decay configuration
DECAY_HALF_LIFE_DAYS = 30  # Patterns lose 50% confidence after 30 activity days
MIN_CONFIDENCE_FOR_INJECTION = 0.60  # Minimum confidence to inject into prompt


class AwarenessStore:
    """Persistent store for behavioral awareness patterns.

    Thread-safe for concurrent access (3.14t compatible).

    Example:
        >>> store = AwarenessStore.load(Path(".sunwell/awareness"))
        >>> store.add_patterns(new_patterns)
        >>> significant = store.get_significant(limit=5)
        >>> store.save()
    """

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize awareness store.

        Args:
            base_path: Storage directory (defaults to .sunwell/awareness)
        """
        self._base_path = base_path or DEFAULT_AWARENESS_DIR
        self._patterns: dict[str, AwarenessPattern] = {}
        self._lock = threading.Lock()

    @property
    def patterns_file(self) -> Path:
        """Path to patterns JSONL file."""
        return self._base_path / PATTERNS_FILE

    def add_pattern(self, pattern: AwarenessPattern) -> None:
        """Add or merge a pattern (thread-safe).

        If pattern with same ID exists, merges using with_reinforcement.

        Args:
            pattern: Pattern to add
        """
        with self._lock:
            existing = self._patterns.get(pattern.id)
            if existing:
                # Merge with existing pattern
                merged = existing.with_reinforcement(
                    new_metric=pattern.metric,
                    new_samples=pattern.sample_size,
                )
                self._patterns[pattern.id] = merged
                logger.debug(
                    "Reinforced pattern %s (samples: %d -> %d)",
                    pattern.id[:8],
                    existing.sample_size,
                    merged.sample_size,
                )
            else:
                self._patterns[pattern.id] = pattern
                logger.debug("Added new pattern %s: %s", pattern.id[:8], pattern.observation)

    def add_patterns(self, patterns: list[AwarenessPattern]) -> int:
        """Add multiple patterns (thread-safe).

        Args:
            patterns: Patterns to add

        Returns:
            Number of patterns added/updated
        """
        for pattern in patterns:
            self.add_pattern(pattern)
        return len(patterns)

    def get_pattern(self, pattern_id: str) -> AwarenessPattern | None:
        """Get pattern by ID (thread-safe).

        Args:
            pattern_id: Pattern ID to look up

        Returns:
            Pattern or None if not found
        """
        with self._lock:
            return self._patterns.get(pattern_id)

    def get_all(self) -> list[AwarenessPattern]:
        """Get all patterns (thread-safe).

        Returns:
            Copy of all patterns
        """
        with self._lock:
            return list(self._patterns.values())

    def get_significant(
        self,
        limit: int = 5,
        activity_day: int | None = None,
    ) -> list[AwarenessPattern]:
        """Get significant patterns for prompt injection (thread-safe).

        Returns patterns that are:
        - Significant (above threshold for their type)
        - Not too decayed (confidence above minimum)

        Args:
            limit: Maximum patterns to return
            activity_day: Current activity day for decay calculation

        Returns:
            List of significant patterns, sorted by confidence
        """
        with self._lock:
            significant: list[AwarenessPattern] = []

            for pattern in self._patterns.values():
                if not pattern.is_significant:
                    continue

                # Apply decay if activity_day provided
                effective_confidence = pattern.confidence
                if activity_day is not None:
                    days_since_access = activity_day - pattern.activity_day_accessed
                    if days_since_access > 0:
                        # Exponential decay
                        decay_factor = 0.5 ** (days_since_access / DECAY_HALF_LIFE_DAYS)
                        effective_confidence *= decay_factor

                if effective_confidence >= MIN_CONFIDENCE_FOR_INJECTION:
                    significant.append(pattern)

            # Sort by confidence (highest first)
            significant.sort(key=lambda p: p.confidence, reverse=True)

            return significant[:limit]

    def get_by_type(self, pattern_type: PatternType) -> list[AwarenessPattern]:
        """Get all patterns of a specific type (thread-safe).

        Args:
            pattern_type: Type to filter by

        Returns:
            Patterns of the specified type
        """
        with self._lock:
            return [
                p for p in self._patterns.values()
                if p.pattern_type == pattern_type
            ]

    def mark_accessed(self, pattern_ids: list[str], activity_day: int) -> None:
        """Mark patterns as accessed (for decay tracking).

        Args:
            pattern_ids: IDs of accessed patterns
            activity_day: Current activity day
        """
        with self._lock:
            for pid in pattern_ids:
                if pid in self._patterns:
                    self._patterns[pid] = self._patterns[pid].with_access(activity_day)

    def prune_decayed(self, activity_day: int, threshold: float = 0.30) -> int:
        """Remove patterns that have decayed below threshold.

        Args:
            activity_day: Current activity day
            threshold: Minimum effective confidence to keep

        Returns:
            Number of patterns removed
        """
        with self._lock:
            to_remove: list[str] = []

            for pid, pattern in self._patterns.items():
                days_since_access = activity_day - pattern.activity_day_accessed
                if days_since_access > 0:
                    decay_factor = 0.5 ** (days_since_access / DECAY_HALF_LIFE_DAYS)
                    effective_confidence = pattern.confidence * decay_factor

                    if effective_confidence < threshold:
                        to_remove.append(pid)

            for pid in to_remove:
                del self._patterns[pid]

            if to_remove:
                logger.info("Pruned %d decayed awareness patterns", len(to_remove))

            return len(to_remove)

    def save(self) -> Path | None:
        """Save patterns to disk (thread-safe, atomic).

        Uses atomic write to prevent corruption on crash.

        Returns:
            Path to saved file, or None on error
        """
        self._base_path.mkdir(parents=True, exist_ok=True)

        with self._lock:
            patterns_list = list(self._patterns.values())

        # Build content first
        lines = [json.dumps(pattern.to_dict()) + "\n" for pattern in patterns_list]
        content = "".join(lines)

        # Atomic write: temp file + rename
        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix="patterns_",
                dir=self._base_path,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, self.patterns_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            logger.debug("Saved %d awareness patterns to %s", len(patterns_list), self.patterns_file)
            return self.patterns_file
        except OSError as e:
            logger.error("Failed to save awareness patterns: %s", e)
            return None

    @classmethod
    def load(cls, base_path: Path | None = None) -> "AwarenessStore":
        """Load store from disk.

        Creates empty store if file doesn't exist.

        Args:
            base_path: Storage directory

        Returns:
            Loaded AwarenessStore
        """
        store = cls(base_path)

        if not store.patterns_file.exists():
            return store

        try:
            with open(store.patterns_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        pattern = AwarenessPattern.from_dict(data)
                        store._patterns[pattern.id] = pattern
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning("Failed to parse pattern: %s", e)

            logger.debug("Loaded %d awareness patterns from %s", len(store._patterns), store.patterns_file)
        except OSError as e:
            logger.warning("Failed to load awareness patterns: %s", e)

        return store

    def __len__(self) -> int:
        """Number of patterns in store."""
        with self._lock:
            return len(self._patterns)

    def __contains__(self, pattern_id: str) -> bool:
        """Check if pattern exists."""
        with self._lock:
            return pattern_id in self._patterns


def load_awareness_for_session(cwd: Path, activity_day: int = 0) -> list[AwarenessPattern]:
    """Load significant awareness patterns for session start.

    Convenience function for session initialization.

    Args:
        cwd: Working directory
        activity_day: Current activity day for decay calculation

    Returns:
        List of significant patterns for prompt injection
    """
    awareness_dir = cwd / ".sunwell" / "awareness"
    store = AwarenessStore.load(awareness_dir)

    patterns = store.get_significant(limit=5, activity_day=activity_day)

    # Mark as accessed for decay tracking
    if patterns:
        store.mark_accessed([p.id for p in patterns], activity_day)
        store.save()

    return patterns
