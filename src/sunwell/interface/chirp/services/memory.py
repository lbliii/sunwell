"""Memory and learning management service for Chirp interface."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryService:
    """Service for memory/learning management."""

    def __init__(self, workspace: Path | None = None):
        """Initialize memory service.

        Args:
            workspace: Workspace path (defaults to current directory)
        """
        from sunwell.memory.facade.persistent import PersistentMemory

        self.workspace = workspace or Path.cwd()
        try:
            self.memory = PersistentMemory.load(self.workspace)
        except Exception as e:
            logger.warning("Failed to load memory: %s", e)
            self.memory = PersistentMemory.empty(self.workspace)

    def list_memories(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent learnings/memories.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of memory dicts
        """
        memories = []

        # Get learnings from simulacrum store
        if self.memory.simulacrum:
            try:
                # List simulacrums
                manager = getattr(self.memory.simulacrum, "_manager", None)
                if manager:
                    simulacrums = manager.list_simulacrums()

                    for sim_meta in simulacrums[:limit]:
                        # Load simulacrum to get learnings
                        sim = manager.load_simulacrum(sim_meta.name)
                        if sim and hasattr(sim, "planning_context"):
                            for learning in sim.planning_context.all_learnings()[:10]:
                                memories.append({
                                    "id": learning.id if hasattr(learning, "id") else f"l-{len(memories)}",
                                    "content": str(learning.content if hasattr(learning, "content") else learning),
                                    "type": "learning",
                                    "confidence": getattr(learning, "confidence", 1.0),
                                    "timestamp": getattr(learning, "timestamp", 0.0),
                                    "source": f"simulacrum:{sim_meta.name}",
                                })

                        if len(memories) >= limit:
                            break
            except Exception as e:
                logger.debug("Error loading simulacrum learnings: %s", e)

        # Get patterns from pattern profile
        if self.memory.patterns and len(memories) < limit:
            try:
                patterns = self.memory.patterns.list_patterns()
                for pattern in patterns[: limit - len(memories)]:
                    memories.append({
                        "id": f"p-{len(memories)}",
                        "content": pattern.get("description", str(pattern)),
                        "type": "pattern",
                        "confidence": 1.0,
                        "timestamp": pattern.get("timestamp", 0.0),
                        "source": "patterns",
                    })
            except Exception as e:
                logger.debug("Error loading patterns: %s", e)

        # Get recent decisions
        if self.memory.decisions and len(memories) < limit:
            try:
                decisions = self.memory.decisions.list_decisions()
                for decision in decisions[: limit - len(memories)]:
                    memories.append({
                        "id": decision.get("id", f"d-{len(memories)}"),
                        "content": decision.get("summary", str(decision)),
                        "type": "decision",
                        "confidence": 1.0,
                        "timestamp": decision.get("timestamp", 0.0),
                        "source": "decisions",
                    })
            except Exception as e:
                logger.debug("Error loading decisions: %s", e)

        # If no real memories, return placeholder
        if not memories:
            return [
                {
                    "id": "placeholder",
                    "content": "No memories found. Complete tasks to build memory.",
                    "type": "system",
                    "confidence": 1.0,
                    "timestamp": 0.0,
                    "source": "system",
                }
            ]

        return memories[:limit]
