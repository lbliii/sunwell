"""GitHub repository search for magnetic research.

Uses GitHub Search API to find relevant repositories for pattern analysis.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

import httpx

from sunwell.research.types import RepoResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubSearcher:
    """Search GitHub for repositories matching a query.

    Uses the GitHub Search API with optional authentication for higher rate limits.
    """

    def __init__(self, token: str | None = None) -> None:
        """Initialize with optional GitHub token.

        Args:
            token: GitHub personal access token. If not provided, uses
                   GITHUB_TOKEN environment variable. Without a token,
                   rate limits are 60 requests/hour vs 5000 with auth.
        """
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

            self._client = httpx.AsyncClient(
                base_url=GITHUB_API_BASE,
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def search(
        self,
        query: str,
        language: str | None = None,
        min_stars: int = 50,
        max_results: int = 5,
        sort: str = "stars",
    ) -> list[RepoResult]:
        """Search GitHub for repositories.

        Args:
            query: Search query (e.g., "todo app", "auth system").
            language: Filter by programming language (e.g., "python", "typescript").
            min_stars: Minimum stars filter.
            max_results: Maximum number of results to return.
            sort: Sort order ("stars", "forks", "updated", "best-match").

        Returns:
            List of matching repositories, sorted by relevance.
        """
        # Build search query
        q_parts = [query]
        if language:
            q_parts.append(f"language:{language}")
        if min_stars > 0:
            q_parts.append(f"stars:>={min_stars}")

        q = " ".join(q_parts)

        client = await self._get_client()

        try:
            response = await client.get(
                "/search/repositories",
                params={
                    "q": q,
                    "sort": sort,
                    "order": "desc",
                    "per_page": min(max_results, 100),
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub search failed: %s", e)
            if e.response.status_code == 403:
                logger.error("Rate limit exceeded. Consider setting GITHUB_TOKEN.")
            return []
        except httpx.RequestError as e:
            logger.error("GitHub request failed: %s", e)
            return []

        results: list[RepoResult] = []
        for item in data.get("items", [])[:max_results]:
            try:
                updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                result = RepoResult(
                    full_name=item["full_name"],
                    description=item.get("description"),
                    stars=item.get("stargazers_count", 0),
                    language=item.get("language"),
                    updated_at=updated_at,
                    clone_url=item["clone_url"],
                    default_branch=item.get("default_branch", "main"),
                    topics=tuple(item.get("topics", [])),
                )
                results.append(result)
            except (KeyError, ValueError) as e:
                logger.warning("Failed to parse repo result: %s", e)
                continue

        return results

    async def search_by_topic(
        self,
        topic: str,
        language: str | None = None,
        min_stars: int = 100,
        max_results: int = 5,
    ) -> list[RepoResult]:
        """Search repositories by topic tag.

        Args:
            topic: Topic to search for (e.g., "svelte", "fastapi").
            language: Optional language filter.
            min_stars: Minimum stars filter.
            max_results: Maximum results.

        Returns:
            List of repositories with the given topic.
        """
        query = f"topic:{topic}"
        return await self.search(
            query=query,
            language=language,
            min_stars=min_stars,
            max_results=max_results,
        )

    async def get_repo_info(self, full_name: str) -> RepoResult | None:
        """Get detailed information about a specific repository.

        Args:
            full_name: Repository full name (e.g., "owner/repo").

        Returns:
            Repository information or None if not found.
        """
        client = await self._get_client()

        try:
            response = await client.get(f"/repos/{full_name}")
            response.raise_for_status()
            item = response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to get repo info for %s: %s", full_name, e)
            return None

        try:
            updated_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
            return RepoResult(
                full_name=item["full_name"],
                description=item.get("description"),
                stars=item.get("stargazers_count", 0),
                language=item.get("language"),
                updated_at=updated_at,
                clone_url=item["clone_url"],
                default_branch=item.get("default_branch", "main"),
                topics=tuple(item.get("topics", [])),
            )
        except (KeyError, ValueError) as e:
            logger.error("Failed to parse repo info: %s", e)
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> GitHubSearcher:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
