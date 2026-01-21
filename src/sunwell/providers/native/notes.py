"""Sunwell Native Notes Provider (RFC-075).

Local notes stored as markdown in .sunwell/notes/ directory.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sunwell.providers.base import Note, NotesProvider


class SunwellNotes(NotesProvider):
    """Sunwell-native notes stored as markdown in .sunwell/notes/."""

    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "notes"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "_index.json"

    def _load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_index(self, index: dict[str, dict]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2))

    async def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search notes by content."""
        index = self._load_index()
        results = []
        query_lower = query.lower()

        for note_id, meta in index.items():
            note_path = self.dir / f"{note_id}.md"
            if note_path.exists():
                content = note_path.read_text()

                # Simple search: title or content contains query
                if query_lower in meta["title"].lower() or query_lower in content.lower():
                    results.append(
                        Note(
                            id=note_id,
                            title=meta["title"],
                            content=content,
                            created=datetime.fromisoformat(meta["created"]),
                            modified=datetime.fromisoformat(meta["modified"]),
                            tags=tuple(meta.get("tags", [])),
                        )
                    )

        # Sort by relevance (title match > content match) then by modified
        results.sort(
            key=lambda n: (query_lower not in n.title.lower(), -n.modified.timestamp())
        )
        return results[:limit]

    async def get_recent(self, limit: int = 10) -> list[Note]:
        """Get recently modified notes."""
        index = self._load_index()

        # Sort by modified time descending
        sorted_ids = sorted(
            index.keys(),
            key=lambda k: index[k]["modified"],
            reverse=True,
        )[:limit]

        results = []
        for note_id in sorted_ids:
            note = await self.get_by_id(note_id)
            if note:
                results.append(note)

        return results

    async def get_by_id(self, note_id: str) -> Note | None:
        """Get a specific note."""
        index = self._load_index()

        if note_id not in index:
            return None

        meta = index[note_id]
        note_path = self.dir / f"{note_id}.md"

        if not note_path.exists():
            return None

        return Note(
            id=note_id,
            title=meta["title"],
            content=note_path.read_text(),
            created=datetime.fromisoformat(meta["created"]),
            modified=datetime.fromisoformat(meta["modified"]),
            tags=tuple(meta.get("tags", [])),
        )

    async def create(
        self, title: str, content: str, tags: list[str] | None = None
    ) -> Note:
        """Create a new note."""
        index = self._load_index()

        note_id = str(uuid4())
        now = datetime.now()

        # Save content
        note_path = self.dir / f"{note_id}.md"
        note_path.write_text(content)

        # Update index
        index[note_id] = {
            "title": title,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "tags": tags or [],
        }
        self._save_index(index)

        return Note(
            id=note_id,
            title=title,
            content=content,
            created=now,
            modified=now,
            tags=tuple(tags or []),
        )

    async def update(self, note: Note) -> Note:
        """Update an existing note."""
        index = self._load_index()

        if note.id not in index:
            raise ValueError(f"Note not found: {note.id}")

        now = datetime.now()

        # Save content
        note_path = self.dir / f"{note.id}.md"
        note_path.write_text(note.content)

        # Update index
        index[note.id] = {
            "title": note.title,
            "created": index[note.id]["created"],
            "modified": now.isoformat(),
            "tags": list(note.tags),
        }
        self._save_index(index)

        return Note(
            id=note.id,
            title=note.title,
            content=note.content,
            created=note.created,
            modified=now,
            tags=note.tags,
        )
