"""Convergence - Shared Working Memory for the Naaru Architecture (RFC-019).

The Convergence is the shared working memory with limited capacity (7±2 slots),
inspired by Miller's Law from cognitive psychology.

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← This module
        ║  [slot1] [slot2] ... [slot7] ║
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

The Convergence holds pre-fetched context that Shards gather while the model thinks.
Items are evicted based on relevance when capacity is reached.

Naming Rationale:
    In Naaru lore, convergence represents shared purpose and unified thought.
    The Convergence is where all components share their findings.

Example:
    >>> from sunwell.naaru.convergence import Convergence, Slot
    >>>
    >>> convergence = Convergence(capacity=7)
    >>>
    >>> # Add a memory slot
    >>> await convergence.add(Slot(
    ...     id="memories:error_handling",
    ...     content=["Use specific exceptions", "Include context"],
    ...     relevance=0.9,
    ... ))
    >>>
    >>> # Retrieve when needed
    >>> slot = await convergence.get("memories:error_handling")
    >>> print(slot.content)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SlotSource(Enum):
    """Source of a slot's content - which Shard populated it."""

    MEMORY_FETCHER = "memory_fetcher"
    CONTEXT_PREPARER = "context_preparer"
    QUICK_CHECKER = "quick_checker"
    LOOKAHEAD = "lookahead"
    CONSOLIDATOR = "consolidator"
    COMPOSITOR = "compositor"  # RFC-082: UI composition prediction
    USER = "user"
    NAARU = "naaru"


@dataclass
class Slot:
    """A slot in the Convergence (working memory).

    Attributes:
        id: Unique identifier for this slot
        content: The slot's content (any type)
        relevance: How relevant to current task (0.0-1.0)
        source: Which component populated this slot
        ready: Whether the content is ready to use
        ttl: Time-to-live in seconds (None = no expiry)
    """

    id: str
    content: Any
    relevance: float = 1.0
    source: SlotSource | None = None
    ready: bool = True
    ttl: float | None = None

    # Timestamp for TTL calculation
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


@dataclass
class Convergence:
    """Shared working memory with limited capacity (7±2 slots).

    Like human working memory:
    - Limited capacity (can't hold everything)
    - Items decay if not refreshed (via TTL)
    - Most relevant items stay
    - Shards can pre-load anticipated needs

    The Convergence is the central meeting point where all Naaru
    components share their findings.

    Example:
        >>> convergence = Convergence(capacity=7)
        >>>
        >>> # Shard adds memory context
        >>> await convergence.add(Slot(
        ...     id="memories:testing",
        ...     content=["Use pytest fixtures", "Test edge cases"],
        ...     relevance=0.9,
        ...     source=SlotSource.MEMORY_FETCHER,
        ... ))
        >>>
        >>> # Synthesis retrieves it
        >>> slot = await convergence.get("memories:testing")
        >>> if slot and slot.ready:
        ...     memories = slot.content
    """

    capacity: int = 7  # Miller's magical number (7±2)
    slots: list[Slot] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Statistics
    _stats: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._stats = {
            "adds": 0,
            "evictions": 0,
            "hits": 0,
            "misses": 0,
        }

    async def add(self, slot: Slot) -> bool:
        """Add item to working memory, evicting if at capacity.

        If a slot with the same ID exists, it will be updated.
        If at capacity, the least relevant slot is evicted.

        Args:
            slot: The slot to add

        Returns:
            True if added successfully
        """
        async with self._lock:
            self._stats["adds"] += 1

            # Check if already present - update if so
            for i, existing in enumerate(self.slots):
                if existing.id == slot.id:
                    self.slots[i] = slot
                    return True

            # At capacity - evict least relevant
            if len(self.slots) >= self.capacity:
                self.slots.sort(key=lambda s: s.relevance)
                self.slots.pop(0)
                self._stats["evictions"] += 1

            self.slots.append(slot)
            return True

    async def get(self, slot_id: str) -> Slot | None:
        """Get item from working memory by ID.

        Args:
            slot_id: The slot's unique identifier

        Returns:
            The slot if found, None otherwise
        """
        async with self._lock:
            for slot in self.slots:
                if slot.id == slot_id:
                    # Check TTL
                    if slot.ttl is not None:
                        now = asyncio.get_event_loop().time()
                        if now - slot.created_at > slot.ttl:
                            # Expired
                            self.slots.remove(slot)
                            self._stats["misses"] += 1
                            return None

                    self._stats["hits"] += 1
                    return slot

            self._stats["misses"] += 1
            return None

    async def get_all_ready(self) -> list[Slot]:
        """Get all ready items from working memory.

        Returns:
            List of slots that are ready to use
        """
        async with self._lock:
            return [s for s in self.slots if s.ready]

    async def get_by_source(self, source: SlotSource) -> list[Slot]:
        """Get all items from a specific source.

        Args:
            source: The slot source to filter by

        Returns:
            List of slots from that source
        """
        async with self._lock:
            return [s for s in self.slots if s.source == source]

    async def update_relevance(self, slot_id: str, relevance: float) -> bool:
        """Update the relevance score of a slot.

        Higher relevance = less likely to be evicted.

        Args:
            slot_id: The slot's unique identifier
            relevance: New relevance score (0.0-1.0)

        Returns:
            True if slot was found and updated
        """
        async with self._lock:
            for slot in self.slots:
                if slot.id == slot_id:
                    slot.relevance = max(0.0, min(1.0, relevance))
                    return True
            return False

    async def mark_ready(self, slot_id: str, ready: bool = True) -> bool:
        """Mark a slot as ready or not ready.

        Args:
            slot_id: The slot's unique identifier
            ready: Whether the slot is ready

        Returns:
            True if slot was found and updated
        """
        async with self._lock:
            for slot in self.slots:
                if slot.id == slot_id:
                    slot.ready = ready
                    return True
            return False

    async def remove(self, slot_id: str) -> bool:
        """Remove a slot from working memory.

        Args:
            slot_id: The slot's unique identifier

        Returns:
            True if slot was found and removed
        """
        async with self._lock:
            for slot in self.slots:
                if slot.id == slot_id:
                    self.slots.remove(slot)
                    return True
            return False

    async def clear(self) -> None:
        """Clear all slots from working memory."""
        async with self._lock:
            self.slots.clear()

    async def cleanup_expired(self) -> int:
        """Remove all expired slots.

        Returns:
            Number of slots removed
        """
        async with self._lock:
            now = asyncio.get_event_loop().time()
            expired = [
                s for s in self.slots
                if s.ttl is not None and now - s.created_at > s.ttl
            ]
            for slot in expired:
                self.slots.remove(slot)
            return len(expired)

    def get_stats(self) -> dict:
        """Get convergence statistics.

        Returns:
            Dict with adds, evictions, hits, misses, current_size
        """
        return {
            **self._stats,
            "current_size": len(self.slots),
            "capacity": self.capacity,
            "utilization": len(self.slots) / self.capacity if self.capacity > 0 else 0,
        }

    async def snapshot(self) -> list[dict]:
        """Get a snapshot of all slots for debugging.

        Returns:
            List of slot info dicts
        """
        async with self._lock:
            return [
                {
                    "id": s.id,
                    "relevance": s.relevance,
                    "source": s.source.value if s.source else None,
                    "ready": s.ready,
                    "content_type": type(s.content).__name__,
                    "content_preview": str(s.content)[:100] if s.content else None,
                }
                for s in sorted(self.slots, key=lambda x: -x.relevance)
            ]


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate the Convergence working memory."""
    print("=" * 60)
    print("Convergence (Working Memory) Demo")
    print("=" * 60)

    convergence = Convergence(capacity=7)

    print(f"\nCapacity: {convergence.capacity} (Miller's Law)")
    print()

    # Add some slots
    test_slots = [
        Slot(
            id="memories:error_handling",
            content=["Use specific exceptions", "Include context in messages"],
            relevance=0.9,
            source=SlotSource.MEMORY_FETCHER,
        ),
        Slot(
            id="context:testing",
            content={"lens": "team-qa.lens", "embedding": [0.1, 0.2, 0.3]},
            relevance=0.8,
            source=SlotSource.CONTEXT_PREPARER,
        ),
        Slot(
            id="prefetch:documentation",
            content={"description": "Add docstrings", "ready": False},
            relevance=0.5,
            source=SlotSource.LOOKAHEAD,
            ready=False,
        ),
    ]

    print("📥 Adding slots...")
    for slot in test_slots:
        await convergence.add(slot)
        print(f"   Added: {slot.id} (relevance: {slot.relevance})")

    print("\n📊 Current state:")
    snapshot = await convergence.snapshot()
    for s in snapshot:
        ready = "✓" if s["ready"] else "○"
        print(f"   {ready} {s['id']} - {s['relevance']:.1f} - {s['source']}")

    print("\n🔍 Retrieving 'memories:error_handling'...")
    slot = await convergence.get("memories:error_handling")
    if slot:
        print(f"   Found: {slot.content}")

    print("\n📈 Statistics:")
    stats = convergence.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
