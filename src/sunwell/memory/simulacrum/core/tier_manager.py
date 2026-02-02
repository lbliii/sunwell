"""Tier management for recent/compressed/archived turn storage."""

import gzip
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from sunwell.memory.simulacrum.core.config import StorageConfig
from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.turn import Turn, TurnType


class TierManager:
    """Manages recent/compressed/archived tier storage lifecycle for turns."""

    def __init__(
        self,
        base_path: Path,
        config: StorageConfig,
        hot_dag: ConversationDAG,
    ) -> None:
        """Initialize tier manager.

        Args:
            base_path: Base directory for storage
            config: Storage configuration
            hot_dag: Current conversation DAG
        """
        self.base_path = base_path
        self.config = config
        self._hot_dag = hot_dag

    @property
    def hot_path(self) -> Path:
        """Path to recent turns storage."""
        return self.base_path / "turns" / "recent"

    @property
    def warm_path(self) -> Path:
        """Path to compressed turns storage directory."""
        return self.base_path / "turns" / "compressed"

    @property
    def cold_path(self) -> Path:
        """Path to archived turns storage directory."""
        return self.base_path / "turns" / "archived"

    def flush_recent(self, session_id: str) -> None:
        """Flush recent tier to disk."""
        recent_file = self.hot_path / f"{session_id}.json"
        self._hot_dag.save(recent_file)

    def maybe_demote_to_compressed(self) -> None:
        """Move old turns from recent to compressed storage."""
        if len(self._hot_dag.turns) <= self.config.hot_max_turns:
            return

        # Find oldest turns to demote
        turns_by_time = sorted(
            self._hot_dag.turns.values(),
            key=lambda t: t.timestamp,
        )

        to_demote = turns_by_time[:len(turns_by_time) - self.config.hot_max_turns]

        # Save to compressed storage
        for turn in to_demote:
            self._save_to_compressed(turn)
            # Don't remove from DAG - keep structure, just mark as demoted
            self._hot_dag.compressed.add(turn.id)

    def update_hot_dag(self, hot_dag: ConversationDAG) -> None:
        """Update the hot DAG reference (needed when DAG is replaced)."""
        self._hot_dag = hot_dag

    def _save_to_compressed(self, turn: Turn) -> None:
        """Save a turn to compressed storage."""
        # Use date-based sharding for compressed storage
        date_str = turn.timestamp[:10]  # YYYY-MM-DD
        shard_path = self.warm_path / f"{date_str}.jsonl"

        with open(shard_path, "a") as f:
            data = {
                "id": turn.id,
                "content": turn.content,
                "turn_type": turn.turn_type.value,
                "timestamp": turn.timestamp,
                "parent_ids": list(turn.parent_ids),
            }
            f.write(json.dumps(data) + "\n")

    def move_to_archived(self, older_than_hours: int | None = None) -> int:
        """Archive old compressed storage to archived (further compressed)."""
        hours = older_than_hours or self.config.warm_max_age_hours
        cutoff = datetime.now() - timedelta(hours=hours)
        moved = 0

        for shard_file in self.warm_path.glob("*.jsonl"):
            # Parse date from filename
            try:
                file_date = datetime.strptime(shard_file.stem, "%Y-%m-%d")
            except ValueError:
                continue

            if file_date < cutoff:
                # Move to cold storage
                cold_dest = self.cold_path / shard_file.name

                if self.config.cold_compression:
                    # Compress with zstd if available
                    try:
                        import zstd
                        with open(shard_file, "rb") as src:
                            compressed = zstd.compress(src.read())
                        with open(cold_dest.with_suffix(".jsonl.zst"), "wb") as dst:
                            dst.write(compressed)
                    except ImportError:
                        # Fall back to gzip
                        with (
                            open(shard_file, "rb") as src,
                            gzip.open(cold_dest.with_suffix(".jsonl.gz"), "wb") as dst,
                        ):
                            dst.write(src.read())
                else:
                    shutil.move(shard_file, cold_dest)

                # Remove original
                shard_file.unlink(missing_ok=True)
                moved += 1

        return moved

    def retrieve_from_compressed(self, turn_id: str) -> Turn | None:
        """Retrieve a specific turn from compressed storage."""
        for shard_file in self.warm_path.glob("*.jsonl"):
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if data["id"] == turn_id:
                        return Turn(
                            content=data["content"],
                            turn_type=TurnType(data["turn_type"]),
                            timestamp=data["timestamp"],
                            parent_ids=tuple(data.get("parent_ids", [])),
                        )
        return None

    def search_compressed(self, query: str, limit: int = 10) -> list[Turn]:
        """Simple text search over compressed storage."""
        query_lower = query.lower()
        matches = []

        for shard_file in self.warm_path.glob("*.jsonl"):
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if query_lower in data["content"].lower():
                        turn = Turn(
                            content=data["content"],
                            turn_type=TurnType(data["turn_type"]),
                            timestamp=data["timestamp"],
                            parent_ids=tuple(data.get("parent_ids", [])),
                        )
                        matches.append(turn)
                        if len(matches) >= limit:
                            return matches

        return matches

    def cleanup_dead_ends(self, dead_end_ids: set[str]) -> int:
        """Remove dead end turns from compressed/archived storage."""
        if not dead_end_ids:
            return 0

        removed = 0

        # Clean compressed storage
        for shard_file in self.warm_path.glob("*.jsonl"):
            lines_to_keep = []
            with open(shard_file) as f:
                for line in f:
                    data = json.loads(line)
                    if data["id"] not in dead_end_ids:
                        lines_to_keep.append(line)
                    else:
                        removed += 1

            with open(shard_file, "w") as f:
                f.writelines(lines_to_keep)

        return removed
