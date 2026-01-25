"""Git utilities for multi-instance coordination (RFC-051).

Async wrappers for git operations used by workers and coordinator.
"""

import asyncio
import contextlib
import subprocess
from pathlib import Path


async def run_git(root: Path, args: list[str]) -> str:
    """Run a git command asynchronously.

    Args:
        root: Repository root directory
        args: Git command arguments (e.g., ["status", "--porcelain"])

    Returns:
        Command stdout as string

    Raises:
        subprocess.CalledProcessError: If git command fails
    """
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode,
            ["git", *args],
            stdout,
            stderr,
        )

    return stdout.decode()


async def get_current_branch(root: Path) -> str:
    """Get the current git branch name.

    Args:
        root: Repository root directory

    Returns:
        Current branch name
    """
    result = await run_git(root, ["branch", "--show-current"])
    return result.strip()


async def is_working_dir_clean(root: Path) -> bool:
    """Check if working directory is clean.

    Args:
        root: Repository root directory

    Returns:
        True if no uncommitted changes
    """
    status = await run_git(root, ["status", "--porcelain"])
    return not status.strip()


async def create_branch(root: Path, branch_name: str) -> None:
    """Create and checkout a new branch.

    Args:
        root: Repository root directory
        branch_name: Name for the new branch
    """
    await run_git(root, ["checkout", "-b", branch_name])


async def checkout_branch(root: Path, branch_name: str) -> None:
    """Checkout an existing branch.

    Args:
        root: Repository root directory
        branch_name: Branch to checkout
    """
    await run_git(root, ["checkout", branch_name])


async def commit_all(root: Path, message: str) -> str:
    """Stage and commit all changes.

    Args:
        root: Repository root directory
        message: Commit message

    Returns:
        Commit SHA, or empty string if nothing to commit
    """
    # Stage all changes
    await run_git(root, ["add", "-A"])

    # Check if anything to commit
    status = await run_git(root, ["status", "--porcelain"])
    if not status.strip():
        return ""

    # Commit
    await run_git(root, ["commit", "-m", message])

    # Get commit SHA
    sha = await run_git(root, ["rev-parse", "HEAD"])
    return sha.strip()


async def get_branch_first_commit_time(root: Path, branch: str, base: str) -> str:
    """Get the timestamp of the first commit on a branch since base.

    Used for deterministic merge ordering.

    Args:
        root: Repository root directory
        branch: Branch to check
        base: Base branch to compare against

    Returns:
        ISO timestamp of first commit
    """
    result = await run_git(
        root,
        ["log", f"{base}..{branch}", "--format=%cI", "--reverse", "-1"],
    )
    return result.strip()


async def rebase_branch(root: Path, onto: str) -> None:
    """Rebase current branch onto another branch.

    Args:
        root: Repository root directory
        onto: Branch to rebase onto

    Raises:
        subprocess.CalledProcessError: If rebase fails (conflicts)
    """
    await run_git(root, ["rebase", onto])


async def abort_rebase(root: Path) -> None:
    """Abort an in-progress rebase.

    Args:
        root: Repository root directory
    """
    with contextlib.suppress(subprocess.CalledProcessError):
        await run_git(root, ["rebase", "--abort"])


async def merge_ff_only(root: Path, branch: str) -> None:
    """Fast-forward merge a branch.

    Args:
        root: Repository root directory
        branch: Branch to merge

    Raises:
        subprocess.CalledProcessError: If not fast-forwardable
    """
    await run_git(root, ["merge", "--ff-only", branch])


async def delete_branch(root: Path, branch: str, force: bool = False) -> None:
    """Delete a branch.

    Args:
        root: Repository root directory
        branch: Branch to delete
        force: Force delete even if not merged
    """
    flag = "-D" if force else "-d"
    with contextlib.suppress(subprocess.CalledProcessError):
        await run_git(root, ["branch", flag, branch])
