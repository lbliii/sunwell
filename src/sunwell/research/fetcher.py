"""Repository fetcher for magnetic research.

Handles shallow cloning of GitHub repositories for analysis.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.research.types import FetchedRepo, RepoResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# File extensions to include in analysis
SOURCE_EXTENSIONS = {
    # Python
    ".py",
    ".pyi",
    # JavaScript/TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    # Svelte/Vue/React
    ".svelte",
    ".vue",
    # Config files
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    # Documentation
    ".md",
    ".mdx",
    ".rst",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class RepoFetcher:
    """Fetch repositories via shallow clone for analysis.

    Uses git clone --depth=1 for fast, minimal clones.
    """

    def __init__(self, temp_dir: Path | None = None) -> None:
        """Initialize the fetcher.

        Args:
            temp_dir: Base directory for clones. If None, uses system temp.
        """
        self._temp_dir = temp_dir
        self._cloned_repos: list[Path] = []

    async def fetch(
        self,
        repos: list[RepoResult],
        parallel: int = 3,
    ) -> list[FetchedRepo]:
        """Fetch multiple repositories.

        Args:
            repos: List of repositories to clone.
            parallel: Maximum parallel clones.

        Returns:
            List of fetched repositories with local paths.
        """
        # Create semaphore to limit parallelism
        semaphore = asyncio.Semaphore(parallel)

        async def fetch_one(repo: RepoResult) -> FetchedRepo | None:
            async with semaphore:
                return await self._clone_repo(repo)

        tasks = [fetch_one(repo) for repo in repos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        fetched: list[FetchedRepo] = []
        for result in results:
            if isinstance(result, FetchedRepo):
                fetched.append(result)
            elif isinstance(result, Exception):
                logger.error("Failed to fetch repo: %s", result)

        return fetched

    async def fetch_one(self, repo: RepoResult) -> FetchedRepo | None:
        """Fetch a single repository.

        Args:
            repo: Repository to clone.

        Returns:
            Fetched repository or None on failure.
        """
        return await self._clone_repo(repo)

    async def _clone_repo(self, repo: RepoResult) -> FetchedRepo | None:
        """Clone a repository with shallow depth.

        Args:
            repo: Repository to clone.

        Returns:
            FetchedRepo with local path and discovered files.
        """
        # Create unique directory for this repo
        if self._temp_dir:
            base_dir = self._temp_dir
            base_dir.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = Path(tempfile.gettempdir()) / "sunwell_research"
            base_dir.mkdir(parents=True, exist_ok=True)

        # Use repo name as directory (sanitize)
        safe_name = repo.full_name.replace("/", "_")
        clone_dir = base_dir / safe_name

        # Remove if exists
        if clone_dir.exists():
            shutil.rmtree(clone_dir)

        logger.info("Cloning %s to %s", repo.full_name, clone_dir)

        try:
            # Shallow clone with single branch
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                f"--branch={repo.default_branch}",
                repo.clone_url,
                str(clone_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)

            if process.returncode != 0:
                logger.error(
                    "Git clone failed for %s: %s",
                    repo.full_name,
                    stderr.decode() if stderr else "unknown error",
                )
                return None

        except asyncio.TimeoutError:
            logger.error("Git clone timed out for %s", repo.full_name)
            return None
        except FileNotFoundError:
            logger.error("Git not found. Please install git.")
            return None

        self._cloned_repos.append(clone_dir)

        # Discover source files
        files = self._discover_files(clone_dir)
        logger.info("Found %d source files in %s", len(files), repo.full_name)

        return FetchedRepo(
            repo=repo,
            local_path=clone_dir,
            files=tuple(files),
        )

    def _discover_files(self, root: Path) -> list[Path]:
        """Discover source files in a directory.

        Args:
            root: Root directory to scan.

        Returns:
            List of source file paths.
        """
        files: list[Path] = []

        def scan(directory: Path) -> None:
            try:
                for entry in directory.iterdir():
                    if entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        if entry.name not in SKIP_DIRS:
                            scan(entry)
                    elif entry.is_file():
                        if entry.suffix.lower() in SOURCE_EXTENSIONS:
                            files.append(entry)
            except PermissionError:
                pass

        scan(root)
        return sorted(files)

    async def cleanup(self) -> None:
        """Remove all cloned repositories."""
        for repo_dir in self._cloned_repos:
            if repo_dir.exists():
                try:
                    shutil.rmtree(repo_dir)
                    logger.debug("Cleaned up %s", repo_dir)
                except OSError as e:
                    logger.warning("Failed to clean up %s: %s", repo_dir, e)
        self._cloned_repos.clear()

    async def __aenter__(self) -> RepoFetcher:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.cleanup()
