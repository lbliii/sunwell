"""Episode tracking for RFC-022: Learning from past sessions."""

import json
from datetime import datetime
from pathlib import Path

from sunwell.foundation.types.memory import Episode


class EpisodeManager:
    """Manages episode tracking for learning from past sessions."""

    def __init__(self, base_path: Path) -> None:
        """Initialize episode manager.

        Args:
            base_path: Base directory for storage
        """
        self.base_path = base_path
        self._episodes: list[Episode] = []
        self._load_episodes()

    def _load_episodes(self) -> None:
        """Load episodes from disk."""
        episodes_file = self.base_path / "episodes" / "episodes.json"
        if episodes_file.exists():
            try:
                with open(episodes_file) as f:
                    data = json.load(f)
                self._episodes = [
                    Episode(
                        id=ep["id"],
                        summary=ep["summary"],
                        outcome=ep["outcome"],
                        timestamp=ep.get("timestamp", ""),
                        learnings_extracted=tuple(ep.get("learnings_extracted", [])),
                        models_used=tuple(ep.get("models_used", [])),
                        turn_count=ep.get("turn_count", 0),
                    )
                    for ep in data
                ]
            except (json.JSONDecodeError, KeyError):
                self._episodes = []

    def _save_episodes(self) -> None:
        """Save episodes to disk."""
        episodes_file = self.base_path / "episodes" / "episodes.json"
        episodes_file.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "id": ep.id,
                "summary": ep.summary,
                "outcome": ep.outcome,
                "timestamp": ep.timestamp,
                "learnings_extracted": list(ep.learnings_extracted),
                "models_used": list(ep.models_used),
                "turn_count": ep.turn_count,
            }
            for ep in self._episodes
        ]
        with open(episodes_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_episode(
        self,
        summary: str,
        outcome: str,  # succeeded, failed, partial, abandoned
        learnings_extracted: tuple[str, ...] = (),
        models_used: tuple[str, ...] = (),
        turn_count: int = 0,
    ) -> str:
        """Add an episode tracking past problem-solving attempt.

        Episodes help avoid repeating dead ends and learn from past sessions.

        Args:
            summary: Brief description of what was attempted
            outcome: 'succeeded', 'failed', 'partial', or 'abandoned'
            learnings_extracted: Key insights from this episode
            models_used: Models that were used during the episode
            turn_count: Number of turns in the session

        Returns:
            Episode ID
        """
        episode = Episode(
            id=f"ep_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self._episodes)}",
            summary=summary,
            outcome=outcome,
            learnings_extracted=learnings_extracted,
            models_used=models_used,
            turn_count=turn_count,
        )
        self._episodes.append(episode)
        self._save_episodes()
        return episode.id

    def get_episodes(self, limit: int = 50) -> list[Episode]:
        """Get recent episodes.

        Args:
            limit: Maximum episodes to return

        Returns:
            List of episodes, most recent first
        """
        return self._episodes[-limit:][::-1]  # Most recent first

    def get_dead_ends(self) -> list[Episode]:
        """Get failed episodes to avoid repeating mistakes.

        Returns:
            List of episodes with 'failed' outcome
        """
        return [ep for ep in self._episodes if ep.outcome == "failed"]

    def get_successful_patterns(self) -> list[Episode]:
        """Get successful episodes for learning what works.

        Returns:
            List of episodes with 'succeeded' outcome
        """
        return [ep for ep in self._episodes if ep.outcome == "succeeded"]

    def get_episode_by_id(self, episode_id: str) -> Episode | None:
        """Get a specific episode by ID.

        Args:
            episode_id: The episode ID

        Returns:
            Episode if found, None otherwise
        """
        for ep in self._episodes:
            if ep.id == episode_id:
                return ep
        return None
