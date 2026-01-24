"""SmartContext - Graceful degradation from semantic to grep (RFC-108).

Provides context retrieval that works even without embeddings:
1. Semantic index (quality=1.0) - Best, uses embeddings
2. Grep search (quality=0.6) - Fallback, keyword matching
3. File listing (quality=0.3) - Minimal, just shows structure
"""

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.indexing.service import IndexingService


@dataclass
class ContextResult:
    """Result of context retrieval."""

    source: str  # 'semantic', 'grep', 'file_list'
    quality: float  # 0.0-1.0
    content: str
    chunks_used: int = 0


@dataclass
class SmartContext:
    """Context provider that degrades gracefully.

    Fallback chain:
    1. Semantic index (quality=1.0) - Best, uses embeddings
    2. Grep search (quality=0.6) - Fallback, keyword matching
    3. File listing (quality=0.3) - Minimal, just shows structure
    """

    indexer: IndexingService | None
    workspace_root: Path

    async def get_context(self, query: str, max_chunks: int = 5) -> ContextResult:
        """Get best available context for a query.

        Args:
            query: Natural language query.
            max_chunks: Maximum chunks to include.

        Returns:
            ContextResult with content and quality info.
        """
        # Tier 1: Full semantic search (best)
        if self.indexer and self.indexer.is_ready:
            chunks = await self.indexer.query(query, top_k=max_chunks)
            if chunks:
                return ContextResult(
                    source="semantic",
                    quality=1.0,
                    content=self._format_chunks(chunks),
                    chunks_used=len(chunks),
                )

        # Tier 2: Grep-based search (fallback)
        grep_results = await self._grep_search(query)
        if grep_results:
            return ContextResult(
                source="grep",
                quality=0.6,
                content=self._format_grep_results(grep_results),
                chunks_used=len(grep_results),
            )

        # Tier 3: File listing (minimal)
        files = self._list_relevant_files(query)
        return ContextResult(
            source="file_list",
            quality=0.3,
            content=self._format_file_list(files),
            chunks_used=0,
        )

    async def _grep_search(
        self, query: str, max_results: int = 10
    ) -> list[dict]:
        """Fall back to grep-based keyword search.

        Uses ripgrep (rg) for fast searching.

        Args:
            query: Query string.
            max_results: Maximum results.

        Returns:
            List of match dicts.
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        results: list[dict] = []
        for keyword in keywords[:3]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "rg",
                    "--json",
                    "-i",
                    "-C",
                    "2",
                    keyword,
                    str(self.workspace_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                results.extend(self._parse_rg_json(stdout.decode()))
            except Exception:
                pass

        # Deduplicate by file:line
        seen: set[str] = set()
        unique: list[dict] = []
        for r in results:
            key = f"{r['file']}:{r['line']}"
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:max_results]

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract searchable keywords from query.

        Removes common stopwords to focus on meaningful terms.

        Args:
            query: Query string.

        Returns:
            List of keywords.
        """
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "how",
            "does",
            "what",
            "where",
            "when",
            "why",
            "can",
            "do",
            "this",
            "that",
            "it",
            "to",
            "for",
            "in",
            "on",
            "with",
        }
        words = query.lower().split()
        keywords = [w for w in words if w not in stopwords and len(w) > 2]
        return keywords

    def _parse_rg_json(self, output: str) -> list[dict]:
        """Parse ripgrep JSON output.

        Args:
            output: JSON output from rg.

        Returns:
            List of match dicts.
        """
        results: list[dict] = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data.get("data", {})
                    results.append({
                        "file": match_data.get("path", {}).get("text", ""),
                        "line": match_data.get("line_number", 0),
                        "content": match_data.get("lines", {}).get("text", ""),
                    })
            except json.JSONDecodeError:
                continue
        return results

    def _list_relevant_files(
        self, query: str, max_files: int = 20
    ) -> list[Path]:
        """List files that might be relevant based on name.

        Args:
            query: Query string.
            max_files: Maximum files.

        Returns:
            List of file paths.
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        relevant: list[Path] = []
        ignore_dirs = {
            ".git",
            ".sunwell",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
        }

        for path in self.workspace_root.rglob("*"):
            if path.is_file():
                # Skip ignored directories
                if any(d in path.parts for d in ignore_dirs):
                    continue

                name_lower = path.name.lower()
                if any(kw in name_lower for kw in keywords):
                    relevant.append(path)

        return relevant[:max_files]

    def _format_chunks(self, chunks) -> str:
        """Format semantic search results.

        Args:
            chunks: List of CodeChunk objects.

        Returns:
            Formatted markdown string.
        """
        sections: list[str] = ["## Relevant Code\n"]
        for chunk in chunks:
            sections.append(f"### {chunk.reference}\n")
            sections.append(f"```\n{chunk.content}\n```\n")
        return "\n".join(sections)

    def _format_grep_results(self, results: list[dict]) -> str:
        """Format grep results.

        Args:
            results: List of match dicts.

        Returns:
            Formatted markdown string.
        """
        sections: list[str] = ["## Search Results (grep)\n"]
        for r in results:
            sections.append(f"**{r['file']}:{r['line']}**\n")
            sections.append(f"```\n{r['content'].strip()}\n```\n")
        return "\n".join(sections)

    def _format_file_list(self, files: list[Path]) -> str:
        """Format file listing.

        Args:
            files: List of file paths.

        Returns:
            Formatted markdown string.
        """
        if not files:
            return "No relevant files found."

        sections: list[str] = ["## Potentially Relevant Files\n"]
        for f in files:
            try:
                rel = f.relative_to(self.workspace_root)
            except ValueError:
                rel = f
            sections.append(f"- `{rel}`")
        return "\n".join(sections)
