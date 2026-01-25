"""Skill execution caching for incremental runs (RFC-087, RFC-094).

This module implements the caching component of RFC-087: Skill-Lens DAG.
It provides:
1. Content-based cache keys for skill executions
2. Thread-safe O(1) LRU cache for skill outputs (RFC-094)
3. Cache invalidation by skill or content change
"""


import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.planning.skills.types import Skill, SkillOutput


# =============================================================================
# CACHE KEY
# =============================================================================


@dataclass(frozen=True, slots=True)
class SkillCacheKey:
    """Cache key for skill execution results.

    A skill result is valid if:
    1. Skill content hasn't changed (instruction, scripts, etc.)
    2. Input context matches (values of 'requires' keys)
    3. Lens version matches (optional, for strict caching)
    """

    skill_hash: str
    """SHA-256 (truncated) of skill definition (instructions, scripts, templates)."""

    input_hash: str
    """SHA-256 (truncated) of input context values (the 'requires' keys)."""

    lens_version: str | None = None
    """Optional lens version for strict cache invalidation."""

    @classmethod
    def compute(
        cls,
        skill: Skill,
        context: dict[str, Any],
        lens_version: str | None = None,
    ) -> SkillCacheKey:
        """Compute cache key for a skill execution.

        Args:
            skill: The skill to execute
            context: Current execution context
            lens_version: Optional lens version

        Returns:
            Cache key for this execution
        """
        # Hash skill definition
        skill_hasher = hashlib.sha256()
        skill_hasher.update(skill.name.encode())
        skill_hasher.update((skill.instructions or "").encode())
        for script in skill.scripts:
            skill_hasher.update(script.content.encode())
        for template in skill.templates:
            skill_hasher.update(template.content.encode())
        skill_hash = skill_hasher.hexdigest()[:20]  # 80 bits (RFC-094)

        # Hash input context (only the keys this skill requires)
        input_hasher = hashlib.sha256()
        for key in sorted(skill.requires):
            value = context.get(key, "")
            # Hash the string representation (for complex objects)
            input_hasher.update(f"{key}={value!r}".encode())
        input_hash = input_hasher.hexdigest()[:20]  # 80 bits (RFC-094)

        return cls(
            skill_hash=skill_hash,
            input_hash=input_hash,
            lens_version=lens_version,
        )

    def __str__(self) -> str:
        """Human-readable cache key."""
        parts = [self.skill_hash, self.input_hash]
        if self.lens_version:
            parts.append(self.lens_version)
        return ":".join(parts)

    def to_dict(self) -> dict[str, str | None]:
        """Serialize to dictionary for JSON export."""
        return {
            "skill_hash": self.skill_hash,
            "input_hash": self.input_hash,
            "lens_version": self.lens_version,
        }


# =============================================================================
# CACHE ENTRY
# =============================================================================


@dataclass(frozen=True, slots=True)
class SkillCacheEntry:
    """A cached skill execution result."""

    key: SkillCacheKey
    """The cache key for this entry."""

    output: SkillOutput
    """The cached output."""

    skill_name: str
    """Name of the skill that produced this."""

    execution_time_ms: int
    """How long execution took (for skip time estimation)."""


# =============================================================================
# SKILL CACHE
# =============================================================================


class SkillCache:
    """LRU cache for skill execution results.

    Thread-safe via internal locking. Uses OrderedDict for O(1) LRU operations (RFC-094).
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: OrderedDict[str, SkillCacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: SkillCacheKey) -> SkillCacheEntry | None:
        """Get cached entry or None."""
        key_str = str(key)
        with self._lock:
            entry = self._cache.get(key_str)
            if entry:
                self._hits += 1
                # Move to end for LRU — O(1) with OrderedDict
                self._cache.move_to_end(key_str)
            else:
                self._misses += 1
            return entry

    def set(
        self,
        key: SkillCacheKey,
        output: SkillOutput,
        skill_name: str,
        execution_time_ms: int,
    ) -> None:
        """Cache a result."""
        key_str = str(key)
        entry = SkillCacheEntry(
            key=key,
            output=output,
            skill_name=skill_name,
            execution_time_ms=execution_time_ms,
        )

        with self._lock:
            # Evict oldest if at capacity — O(1) with OrderedDict
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            # Remove existing entry if present, then add at end
            if key_str in self._cache:
                del self._cache[key_str]
            self._cache[key_str] = entry

    def has(self, key: SkillCacheKey) -> bool:
        """Check if key exists without updating access order."""
        with self._lock:
            return str(key) in self._cache

    def invalidate_skill(self, skill_name: str) -> int:
        """Invalidate all entries for a skill.

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove = [
                k
                for k, entry in self._cache.items()
                if entry.skill_name == skill_name
            ]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def invalidate_by_hash_prefix(self, skill_hash_prefix: str) -> int:
        """Invalidate entries whose skill_hash starts with prefix.

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove = [
                k for k in self._cache if k.startswith(skill_hash_prefix)
            ]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached results."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> dict[str, int | float]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.hit_rate,
            }

    def estimate_saved_time_ms(self, skill_names: set[str]) -> int:
        """Estimate time saved by skipping cached skills.

        Args:
            skill_names: Skills that would be skipped

        Returns:
            Estimated milliseconds saved
        """
        with self._lock:
            total = 0
            for entry in self._cache.values():
                if entry.skill_name in skill_names:
                    total += entry.execution_time_ms
            return total
