"""Sunwell Native Bookmarks Provider (RFC-078 Phase 2).

Local bookmark storage in .sunwell/bookmarks.json with Chrome import support.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sunwell.models.providers.base import Bookmark, BookmarksProvider

# Pre-compiled regex for Chrome HTML bookmark parsing
_CHROME_HTML_LINK_RE = re.compile(r'<A\s+HREF="([^"]+)"[^>]*>([^<]+)</A>', re.IGNORECASE)


class SunwellBookmarks(BookmarksProvider):
    """Sunwell-native bookmarks stored in .sunwell/bookmarks.json."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize with data directory.

        Args:
            data_dir: The .sunwell data directory.
        """
        self.path = data_dir / "bookmarks.json"
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        """Ensure the bookmarks file exists."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]")

    def _load(self) -> list[dict]:
        """Load bookmarks from JSON file."""
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, bookmarks: list[dict]) -> None:
        """Save bookmarks to JSON file."""
        self.path.write_text(json.dumps(bookmarks, default=str, indent=2))

    def _dict_to_bookmark(self, data: dict) -> Bookmark:
        """Convert dictionary to Bookmark."""
        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        return Bookmark(
            id=data["id"],
            url=data["url"],
            title=data.get("title", data["url"]),
            tags=tuple(data.get("tags", [])),
            description=data.get("description"),
            created=created,
            favicon=data.get("favicon"),
        )

    async def search(self, query: str, limit: int = 20) -> list[Bookmark]:
        """Search bookmarks by title, URL, or description."""
        query_lower = query.lower()
        data = self._load()
        matching: list[Bookmark] = []

        for item in data:
            title = item.get("title", "").lower()
            url = item.get("url", "").lower()
            description = item.get("description", "").lower() if item.get("description") else ""
            tags = " ".join(item.get("tags", [])).lower()

            if (
                query_lower in title
                or query_lower in url
                or query_lower in description
                or query_lower in tags
            ):
                matching.append(self._dict_to_bookmark(item))

            if len(matching) >= limit:
                break

        return matching

    async def get_by_tag(self, tag: str) -> list[Bookmark]:
        """Get all bookmarks with a specific tag."""
        tag_lower = tag.lower()
        data = self._load()
        matching: list[Bookmark] = []

        for item in data:
            item_tags = [t.lower() for t in item.get("tags", [])]
            if tag_lower in item_tags:
                matching.append(self._dict_to_bookmark(item))

        return matching

    async def get_all_tags(self) -> list[str]:
        """Get all unique tags."""
        data = self._load()
        tags: set[str] = set()

        for item in data:
            tags.update(item.get("tags", []))

        return sorted(tags)

    async def add_bookmark(
        self,
        url: str,
        title: str,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> Bookmark:
        """Add a new bookmark."""
        data = self._load()

        # Check for duplicate URL
        for item in data:
            if item["url"] == url:
                # Update existing
                item["title"] = title
                if tags:
                    item["tags"] = tags
                if description:
                    item["description"] = description
                self._save(data)
                return self._dict_to_bookmark(item)

        now = datetime.now()
        new_bookmark = {
            "id": str(uuid4()),
            "url": url,
            "title": title,
            "tags": tags or [],
            "description": description,
            "created": now.isoformat(),
            "favicon": None,
        }

        data.append(new_bookmark)
        self._save(data)
        return self._dict_to_bookmark(new_bookmark)

    async def delete_bookmark(self, bookmark_id: str) -> bool:
        """Delete a bookmark."""
        data = self._load()
        original_len = len(data)
        data = [b for b in data if b["id"] != bookmark_id]
        self._save(data)
        return len(data) < original_len

    async def get_recent(self, limit: int = 20) -> list[Bookmark]:
        """Get recently added bookmarks."""
        data = self._load()

        # Sort by created date descending
        def get_created(item: dict) -> datetime:
            created = item.get("created")
            if isinstance(created, str):
                try:
                    return datetime.fromisoformat(created)
                except ValueError:
                    pass
            return datetime.min

        sorted_data = sorted(data, key=get_created, reverse=True)
        return [self._dict_to_bookmark(item) for item in sorted_data[:limit]]

    async def import_chrome(self, bookmarks_path: Path) -> int:
        """Import bookmarks from Chrome export (HTML or JSON).

        Args:
            bookmarks_path: Path to Chrome bookmarks file.

        Returns:
            Number of bookmarks imported.
        """
        if not bookmarks_path.exists():
            return 0

        content = bookmarks_path.read_text(encoding="utf-8", errors="replace")
        imported = 0

        if bookmarks_path.suffix == ".json":
            imported = await self._import_chrome_json(content)
        elif bookmarks_path.suffix in (".html", ".htm"):
            imported = await self._import_chrome_html(content)

        return imported

    async def _import_chrome_json(self, content: str) -> int:
        """Import from Chrome JSON format (Bookmarks file)."""
        try:
            chrome_data = json.loads(content)
        except json.JSONDecodeError:
            return 0

        bookmarks_to_add: list[tuple[str, str, list[str]]] = []

        def extract_bookmarks(node: dict, folder_path: list[str]) -> None:
            """Recursively extract bookmarks from Chrome JSON."""
            if node.get("type") == "url":
                url = node.get("url", "")
                title = node.get("name", url)
                tags = [p for p in folder_path if p]  # Use folder path as tags
                bookmarks_to_add.append((url, title, tags))
            elif node.get("type") == "folder" or "children" in node:
                folder_name = node.get("name", "")
                new_path = folder_path + [folder_name] if folder_name else folder_path
                for child in node.get("children", []):
                    extract_bookmarks(child, new_path)

        # Chrome JSON has "roots" with bookmark_bar, other, synced
        roots = chrome_data.get("roots", {})
        for root_key in ["bookmark_bar", "other", "synced"]:
            if root_key in roots:
                extract_bookmarks(roots[root_key], [])

        # Add all bookmarks
        for url, title, tags in bookmarks_to_add:
            await self.add_bookmark(url, title, tags)

        return len(bookmarks_to_add)

    async def _import_chrome_html(self, content: str) -> int:
        """Import from Chrome HTML export format."""
        matches = _CHROME_HTML_LINK_RE.findall(content)

        for url, title in matches:
            await self.add_bookmark(url, title.strip())

        return len(matches)
