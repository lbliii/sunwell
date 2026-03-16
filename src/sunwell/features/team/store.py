"""TeamKnowledgeStore stub (team feature removed)."""

from pathlib import Path


class TeamKnowledgeStore:
    """No-op TeamKnowledgeStore stub. Team feature was removed."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root


def get_workspace_team_dir(workspace: Path) -> Path:
    """No-op: return workspace / .sunwell / team."""
    return workspace / ".sunwell" / "team"
