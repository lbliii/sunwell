"""Sunwell Native Git Provider (RFC-078 Phase 2).

Git repository access via subprocess calls to git CLI.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path

from sunwell.providers.base import (
    GitBranch,
    GitCommit,
    GitFileStatus,
    GitProvider,
    GitStatus,
)


class SunwellGit(GitProvider):
    """Sunwell-native git provider using git CLI."""

    def __init__(self, default_repo: Path | None = None) -> None:
        """Initialize with optional default repository path.

        Args:
            default_repo: Default repository path. If None, uses cwd.
        """
        self.default_repo = default_repo

    def _get_repo_path(self, path: str | None) -> Path:
        """Get repository path, using default if not specified."""
        if path:
            return Path(path).resolve()
        if self.default_repo:
            return self.default_repo
        return Path.cwd()

    async def _run_git(
        self, args: list[str], cwd: Path | None = None
    ) -> tuple[int, str, str]:
        """Run a git command and return (returncode, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    async def get_status(self, path: str | None = None) -> GitStatus:
        """Get repository status."""
        repo = self._get_repo_path(path)

        # Get current branch
        code, branch_out, _ = await self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo
        )
        branch = branch_out.strip() if code == 0 else "unknown"

        # Get ahead/behind counts
        ahead, behind = 0, 0
        code, ab_out, _ = await self._run_git(
            ["rev-list", "--left-right", "--count", f"{branch}...@{{u}}"],
            cwd=repo,
        )
        if code == 0 and ab_out.strip():
            parts = ab_out.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])

        # Get file statuses using porcelain format
        code, status_out, _ = await self._run_git(
            ["status", "--porcelain=v1"], cwd=repo
        )

        files: list[GitFileStatus] = []
        if code == 0:
            for line in status_out.splitlines():
                if len(line) < 4:
                    continue
                index_status = line[0]
                worktree_status = line[1]
                file_path = line[3:]

                # Determine status
                if index_status == "?" or worktree_status == "?":
                    status = "untracked"
                    staged = False
                elif index_status == "A":
                    status = "added"
                    staged = True
                elif index_status == "D" or worktree_status == "D":
                    status = "deleted"
                    staged = index_status == "D"
                elif index_status == "R":
                    status = "renamed"
                    staged = True
                elif index_status == "M" or worktree_status == "M":
                    status = "modified"
                    staged = index_status == "M"
                else:
                    status = "modified"
                    staged = index_status != " "

                files.append(GitFileStatus(
                    path=file_path,
                    status=status,
                    staged=staged,
                ))

        return GitStatus(
            branch=branch,
            ahead=ahead,
            behind=behind,
            files=tuple(files),
            is_clean=len(files) == 0,
        )

    async def get_log(
        self, path: str | None = None, limit: int = 50
    ) -> list[GitCommit]:
        """Get commit history."""
        repo = self._get_repo_path(path)

        # Use custom format for parsing
        # Format: hash|short_hash|author|email|timestamp|message
        fmt = "%H|%h|%an|%ae|%ct|%s"
        code, log_out, _ = await self._run_git(
            ["log", f"-{limit}", f"--format={fmt}", "--shortstat"],
            cwd=repo,
        )

        if code != 0:
            return []

        commits: list[GitCommit] = []
        lines = log_out.strip().split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line or "|" not in line:
                i += 1
                continue

            parts = line.split("|", 5)
            if len(parts) < 6:
                i += 1
                continue

            hash_full, short_hash, author, email, timestamp_str, message = parts

            # Parse timestamp
            try:
                timestamp = int(timestamp_str)
                date = datetime.fromtimestamp(timestamp)
            except ValueError:
                date = datetime.now()

            # Look for stat line (files changed)
            files_changed = 0
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if "file" in next_line and "changed" in next_line:
                    match = re.search(r"(\d+) file", next_line)
                    if match:
                        files_changed = int(match.group(1))
                    i += 1

            commits.append(GitCommit(
                hash=hash_full,
                short_hash=short_hash,
                author=author,
                email=email,
                date=date,
                message=message,
                files_changed=files_changed,
            ))
            i += 1

        return commits

    async def get_branches(self, path: str | None = None) -> list[GitBranch]:
        """Get all branches."""
        repo = self._get_repo_path(path)

        # Get local branches
        code, branch_out, _ = await self._run_git(
            ["branch", "-vv", "--format=%(refname:short)|%(upstream:short)|%(HEAD)"],
            cwd=repo,
        )

        branches: list[GitBranch] = []

        if code == 0:
            for line in branch_out.splitlines():
                parts = line.strip().split("|")
                if len(parts) < 3:
                    continue
                name, upstream, head = parts[0], parts[1], parts[2]
                branches.append(GitBranch(
                    name=name,
                    is_current=(head == "*"),
                    is_remote=False,
                    upstream=upstream if upstream else None,
                ))

        # Get remote branches
        code, remote_out, _ = await self._run_git(
            ["branch", "-r", "--format=%(refname:short)"],
            cwd=repo,
        )

        if code == 0:
            for line in remote_out.splitlines():
                name = line.strip()
                if name and "->" not in name:  # Skip HEAD pointers
                    branches.append(GitBranch(
                        name=name,
                        is_current=False,
                        is_remote=True,
                        upstream=None,
                    ))

        return branches

    async def get_diff(
        self, path: str | None = None, ref: str = "HEAD"
    ) -> str:
        """Get diff against a reference."""
        repo = self._get_repo_path(path)

        if ref == "HEAD":
            # Unstaged changes
            code, diff_out, _ = await self._run_git(["diff"], cwd=repo)
        else:
            # Diff against specific ref
            code, diff_out, _ = await self._run_git(
                ["diff", ref], cwd=repo
            )

        return diff_out if code == 0 else ""

    async def search_commits(
        self, query: str, path: str | None = None, limit: int = 20
    ) -> list[GitCommit]:
        """Search commits by message or author."""
        repo = self._get_repo_path(path)

        # Search in commit messages
        fmt = "%H|%h|%an|%ae|%ct|%s"
        code, log_out, _ = await self._run_git(
            ["log", f"-{limit}", f"--format={fmt}", "--grep", query, "-i"],
            cwd=repo,
        )

        commits: list[GitCommit] = []

        if code == 0:
            for line in log_out.splitlines():
                parts = line.strip().split("|", 5)
                if len(parts) < 6:
                    continue

                hash_full, short_hash, author, email, timestamp_str, message = parts

                try:
                    timestamp = int(timestamp_str)
                    date = datetime.fromtimestamp(timestamp)
                except ValueError:
                    date = datetime.now()

                commits.append(GitCommit(
                    hash=hash_full,
                    short_hash=short_hash,
                    author=author,
                    email=email,
                    date=date,
                    message=message,
                    files_changed=0,
                ))

        # Also search by author if not enough results
        if len(commits) < limit:
            remaining = limit - len(commits)
            code, author_out, _ = await self._run_git(
                ["log", f"-{remaining}", f"--format={fmt}", "--author", query, "-i"],
                cwd=repo,
            )

            if code == 0:
                seen = {c.hash for c in commits}
                for line in author_out.splitlines():
                    parts = line.strip().split("|", 5)
                    if len(parts) < 6:
                        continue

                    hash_full = parts[0]
                    if hash_full in seen:
                        continue

                    short_hash, author, email, timestamp_str, message = parts[1:6]

                    try:
                        timestamp = int(timestamp_str)
                        date = datetime.fromtimestamp(timestamp)
                    except ValueError:
                        date = datetime.now()

                    commits.append(GitCommit(
                        hash=hash_full,
                        short_hash=short_hash,
                        author=author,
                        email=email,
                        date=date,
                        message=message,
                        files_changed=0,
                    ))

        return commits
