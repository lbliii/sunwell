"""Recovery System for Autonomy Guardrails (RFC-048).

Git-based recovery ensures every change is revertible.
"""

import asyncio
from datetime import datetime
from pathlib import Path

from sunwell.guardrails.types import (
    FileChange,
    RecoveryOption,
    RollbackResult,
    SessionStart,
)


class GuardrailError(Exception):
    """Error raised by guardrail system."""

    pass


class RecoveryManager:
    """Manage recovery points and rollbacks.

    Strategy:
    1. Commit before each goal (checkpoint)
    2. Tag session start point
    3. On failure/abort, offer revert options

    This complements the existing proposal rollback in mirror/proposals.py:
    - Proposal rollback: Single proposal, stored rollback data
    - Guardrail recovery: Entire session, git-based

    Integration approach:
    - Guardrail recovery complements proposal rollback, doesn't replace it
    - Interactive mode continues using proposal rollback
    - Autonomous mode uses git-based session recovery
    - Both can coexist — git recovery doesn't interfere with proposal state
    """

    def __init__(self, repo_path: Path):
        """Initialize recovery manager.

        Args:
            repo_path: Path to git repository
        """
        self.repo_path = Path(repo_path)
        self.session_tag: str | None = None
        self.goal_commits: list[str] = []
        self._goal_ids: dict[str, str] = {}  # commit -> goal_id

    async def start_session(self) -> SessionStart:
        """Mark session start for potential rollback.

        Creates a git tag at the current HEAD that can be used
        to rollback the entire session if needed.

        Returns:
            SessionStart with session ID and tag

        Raises:
            GuardrailError: If there are uncommitted changes
        """
        # Ensure clean state
        if await self._has_uncommitted_changes():
            raise GuardrailError(
                "Cannot start autonomous session with uncommitted changes. "
                "Please commit or stash your changes first."
            )

        # Create session tag
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_tag = f"sunwell-session-{session_id}"

        await self._run_git(["tag", self.session_tag])

        start_commit = await self._get_head()

        return SessionStart(
            session_id=session_id,
            tag=self.session_tag,
            start_commit=start_commit,
        )

    async def checkpoint_goal(
        self,
        goal_id: str,
        goal_title: str,
        changes: list[FileChange],
    ) -> str:
        """Create checkpoint commit after goal completion.

        Args:
            goal_id: ID of the completed goal
            goal_title: Title for commit message
            changes: List of file changes to commit

        Returns:
            Commit hash
        """
        if not changes:
            # Nothing to commit
            return ""

        # Stage changes
        for change in changes:
            if change.is_deleted:
                await self._run_git(["rm", str(change.path)])
            else:
                await self._run_git(["add", str(change.path)])

        # Check if there are staged changes
        status = await self._run_git(["status", "--porcelain"])
        if not status.strip():
            # Nothing staged
            return ""

        # Commit with metadata
        message = f"[sunwell] {goal_title}\n\nGoal ID: {goal_id}"
        await self._run_git(["commit", "-m", message])

        commit_hash = await self._get_head()
        self.goal_commits.append(commit_hash)
        self._goal_ids[commit_hash] = goal_id

        return commit_hash

    async def rollback_goal(self, goal_id: str) -> RollbackResult:
        """Rollback a specific goal's changes.

        Uses git revert to create a new commit that undoes the goal's changes.
        This is safer than reset as it preserves history.

        Args:
            goal_id: ID of the goal to rollback

        Returns:
            RollbackResult with status
        """
        # Find the commit for this goal
        commit = self._find_goal_commit(goal_id)
        if commit is None:
            return RollbackResult(
                success=False,
                reason=f"Goal commit not found: {goal_id}",
            )

        try:
            # Revert the commit
            await self._run_git(["revert", "--no-commit", commit])
            await self._run_git(["commit", "-m", f"[sunwell] Revert: {goal_id}"])

            return RollbackResult(
                success=True,
                reverted_commit=commit,
                goals_reverted=1,
            )
        except Exception as e:
            # Abort the revert if it failed
            import contextlib

            with contextlib.suppress(Exception):
                await self._run_git(["revert", "--abort"])
            return RollbackResult(
                success=False,
                reason=f"Revert failed: {e}",
            )

    async def rollback_session(self) -> RollbackResult:
        """Rollback entire session to starting point.

        Uses git reset --hard to restore the repository to the session
        start state. This discards all commits made during the session.

        Returns:
            RollbackResult with status
        """
        if not self.session_tag:
            return RollbackResult(
                success=False,
                reason="No session tag found",
            )

        try:
            # Hard reset to session start
            await self._run_git(["reset", "--hard", self.session_tag])

            # Clean untracked files created during session
            await self._run_git(["clean", "-fd"])

            goals_reverted = len(self.goal_commits)
            self.goal_commits = []
            self._goal_ids = {}

            return RollbackResult(
                success=True,
                reverted_commit=self.session_tag,
                goals_reverted=goals_reverted,
            )
        except Exception as e:
            return RollbackResult(
                success=False,
                reason=f"Session rollback failed: {e}",
            )

    async def show_recovery_options(self) -> list[RecoveryOption]:
        """Show available recovery options.

        Returns:
            List of available recovery options
        """
        options: list[RecoveryOption] = []

        # Per-goal reverts (most recent first)
        for i, commit in enumerate(reversed(self.goal_commits)):
            goal_id = self._goal_ids.get(commit, f"goal-{i}")
            options.append(
                RecoveryOption(
                    id=f"revert_{i}",
                    description=f"Revert goal: {goal_id}",
                    action="revert_goal",
                    target=goal_id,
                )
            )

        # Full session rollback
        if self.session_tag:
            options.append(
                RecoveryOption(
                    id="rollback_session",
                    description=f"Rollback entire session ({len(self.goal_commits)} goals)",
                    action="rollback_session",
                    target=self.session_tag,
                )
            )

        return options

    async def get_session_history(self) -> list[dict]:
        """Get history of commits in this session.

        Returns:
            List of commit info dictionaries
        """
        history = []
        for commit in self.goal_commits:
            goal_id = self._goal_ids.get(commit, "unknown")
            # Get commit message
            try:
                msg = await self._run_git(
                    ["log", "-1", "--format=%s", commit]
                )
                history.append({
                    "commit": commit,
                    "goal_id": goal_id,
                    "message": msg.strip(),
                })
            except Exception:
                history.append({
                    "commit": commit,
                    "goal_id": goal_id,
                    "message": "unknown",
                })
        return history

    async def cleanup_session(self) -> None:
        """Clean up session artifacts.

        Removes the session tag. Call this after successful session completion
        when you don't need rollback capability anymore.
        """
        if self.session_tag:
            import contextlib

            with contextlib.suppress(Exception):
                await self._run_git(["tag", "-d", self.session_tag])
            self.session_tag = None

    def _find_goal_commit(self, goal_id: str) -> str | None:
        """Find the commit hash for a goal ID."""
        for commit, gid in self._goal_ids.items():
            if gid == goal_id:
                return commit
        return None

    async def _has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            status = await self._run_git(["status", "--porcelain"])
            return bool(status.strip())
        except Exception:
            return True  # Assume dirty if we can't check

    async def _get_head(self) -> str:
        """Get current HEAD commit hash."""
        return (await self._run_git(["rev-parse", "HEAD"])).strip()

    async def _run_git(self, args: list[str]) -> str:
        """Run a git command.

        Args:
            args: Git command arguments (without 'git')

        Returns:
            Command stdout

        Raises:
            Exception: If command fails
        """
        cmd = ["git", "-C", str(self.repo_path), *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(
                f"Git command failed: {' '.join(args)}\n"
                f"stderr: {stderr.decode()}"
            )

        return stdout.decode()
