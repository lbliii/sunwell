"""Incremental Bootstrap — RFC-050.

Update bootstrap intelligence after git changes.
"""


import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.bootstrap.ownership import OwnershipMap
from sunwell.bootstrap.scanners.git import GitScanner

if TYPE_CHECKING:
    from sunwell.intelligence.context import ProjectContext


@dataclass
class BootstrapUpdate:
    """Result of incremental bootstrap update."""

    new_commits: int
    """Number of new commits processed."""

    new_decisions: int
    """Number of new decisions extracted."""

    files_updated: int
    """Number of files with updated ownership."""


class IncrementalBootstrap:
    """Update bootstrap intelligence after changes.

    Called on session start or after git pull.
    """

    def __init__(self, root: Path, context: ProjectContext):
        """Initialize incremental bootstrap.

        Args:
            root: Project root directory
            context: RFC-045 ProjectContext
        """
        self.root = Path(root)
        self.context = context
        self._state_path = root / ".sunwell" / "bootstrap_state.json"
        self._last_commit = self._read_last_commit()

    def _read_last_commit(self) -> str | None:
        """Read last processed commit from state file."""
        if not self._state_path.exists():
            return None

        try:
            with open(self._state_path) as f:
                state = json.load(f)
            return state.get("last_commit")
        except (json.JSONDecodeError, OSError):
            return None

    def _save_last_commit(self, commit: str) -> None:
        """Save last processed commit to state file."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "last_commit": commit,
            "updated_at": datetime.now().isoformat(),
        }

        with open(self._state_path, "w") as f:
            json.dump(state, f, indent=2)

    async def _get_head_commit(self) -> str | None:
        """Get current HEAD commit SHA."""
        proc = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "HEAD",
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() or None

    async def update_if_needed(self) -> BootstrapUpdate | None:
        """Check for new commits and update intelligence.

        Called on session start or after git pull.

        Returns:
            BootstrapUpdate if changes were made, None if no updates needed
        """
        current_commit = await self._get_head_commit()

        if not current_commit:
            return None  # Not a git repo

        if current_commit == self._last_commit:
            return None  # No changes

        # Get commits since last update
        new_commits = await self._get_commits_since()

        if not new_commits:
            # Update state but no new commits (maybe force push)
            self._save_last_commit(current_commit)
            return BootstrapUpdate(new_commits=0, new_decisions=0, files_updated=0)

        # Extract decisions from new commits only
        new_decisions = await self._extract_decisions_from(new_commits)

        # Update ownership for changed files
        changed_files = self._get_changed_files(new_commits)
        files_updated = await self._update_ownership(changed_files)

        # Record update
        self._save_last_commit(current_commit)

        return BootstrapUpdate(
            new_commits=len(new_commits),
            new_decisions=len(new_decisions),
            files_updated=files_updated,
        )

    async def _get_commits_since(self) -> list[dict]:
        """Get commits since last bootstrap."""
        if not self._last_commit:
            return []

        proc = await asyncio.create_subprocess_exec(
            "git", "log", f"{self._last_commit}..HEAD",
            "--format=%H|%an|%aI|%s",
            "--name-only",
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        commits = []
        current: dict | None = None
        current_files: list[str] = []

        for line in stdout.decode().split("\n"):
            line = line.strip()
            if not line:
                if current:
                    current["files"] = current_files
                    commits.append(current)
                    current = None
                    current_files = []
                continue

            if "|" in line and line.count("|") >= 3:
                if current:
                    current["files"] = current_files
                    commits.append(current)

                parts = line.split("|", 3)
                current = {
                    "sha": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3] if len(parts) > 3 else "",
                }
                current_files = []
            elif current:
                current_files.append(line)

        if current:
            current["files"] = current_files
            commits.append(current)

        return commits

    async def _extract_decisions_from(self, commits: list[dict]) -> list[dict]:
        """Extract decisions from new commits."""
        from sunwell.bootstrap.orchestrator import BootstrapOrchestrator
        from sunwell.bootstrap.types import CommitInfo

        decisions = []

        for commit_data in commits:
            # Convert to CommitInfo-like for processing
            message = commit_data.get("message", "")

            # Use heuristic extraction
            orchestrator = BootstrapOrchestrator(self.root, self.context, use_llm=False)

            commit = CommitInfo(
                sha=commit_data["sha"],
                author=commit_data["author"],
                date=datetime.fromisoformat(commit_data["date"]),
                message=message,
                files_changed=tuple(Path(f) for f in commit_data.get("files", [])),
                is_decision=self._is_decision_commit(message),
                is_fix=False,
                is_refactor=False,
                mentioned_files=(),
            )

            if commit.is_decision:
                decision = orchestrator._heuristic_extract_decision(commit)
                if decision:
                    # Record decision
                    await self.context.decisions.record_decision(
                        category=decision.infer_category(),
                        question=decision.question,
                        choice=decision.choice,
                        rejected=[],
                        rationale=decision.rationale or "From commit",
                        source="bootstrap",
                        confidence=decision.confidence,
                        metadata={
                            "source_type": "commit",
                            "commit_sha": commit_data["sha"][:8],
                            "incremental": True,
                        },
                    )
                    decisions.append(decision)

        return decisions

    def _is_decision_commit(self, message: str) -> bool:
        """Check if commit contains decision language."""
        import re

        patterns = [
            r"\b(decided|chose|selected|switched to|moved to)\b",
            r"\b(instead of|over|rather than)\b",
            r"\b(because|since|due to)\b.*\b(chose|selected|switched)\b",
        ]

        message_lower = message.lower()
        return any(re.search(p, message_lower) for p in patterns)

    def _get_changed_files(self, commits: list[dict]) -> list[Path]:
        """Get all files changed in commits."""
        files = set()
        for commit in commits:
            for f in commit.get("files", []):
                if f.endswith(".py"):
                    files.add(Path(f))
        return list(files)

    async def _update_ownership(self, changed_files: list[Path]) -> int:
        """Update ownership for changed files.

        Only updates blame data for files that changed.
        """
        if not changed_files:
            return 0

        # Get blame for changed files
        scanner = GitScanner(self.root, blame_limit=len(changed_files))
        blame_map = {}

        for file_path in changed_files:
            try:
                regions = await scanner._blame_file(file_path)
                if regions:
                    blame_map[file_path] = regions
            except Exception:
                continue

        if not blame_map:
            return 0

        # Update ownership map
        ownership = OwnershipMap(self.root / ".sunwell" / "intelligence")
        existing_domains = {d.name: d for d in ownership.get_all_domains()}

        # Merge new blame data
        new_domains = ownership.populate_from_blame(blame_map)

        # Count actually updated files
        updated = 0
        for name, domain in new_domains.items():
            is_new = name not in existing_domains
            owner_changed = (
                not is_new and
                domain.primary_owner != existing_domains[name].primary_owner
            )
            if is_new or owner_changed:
                updated += len(domain.files)

        return updated


async def check_for_updates(root: Path, context: ProjectContext) -> BootstrapUpdate | None:
    """Convenience function to check for bootstrap updates.

    Call this at session start:
        update = await check_for_updates(project_root, context)
        if update:
            print(f"Bootstrap updated: {update.new_commits} new commits")
    """
    incremental = IncrementalBootstrap(root, context)
    return await incremental.update_if_needed()
