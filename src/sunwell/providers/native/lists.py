"""Sunwell Native Lists Provider (RFC-075).

Local lists stored in .sunwell/lists/ directory.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sunwell.providers.base import ListItem, ListProvider


class SunwellLists(ListProvider):
    """Sunwell-native lists stored in .sunwell/lists/."""

    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "lists"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _list_path(self, name: str) -> Path:
        # Sanitize list name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.dir / f"{safe_name}.json"

    def _load_list(self, name: str) -> list[dict]:
        path = self._list_path(name)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def _save_list(self, name: str, items: list[dict]) -> None:
        self._list_path(name).write_text(json.dumps(items, indent=2))

    async def get_lists(self) -> list[str]:
        """Get all list names."""
        return [f.stem for f in self.dir.glob("*.json")]

    async def get_items(
        self, list_name: str, include_completed: bool = False
    ) -> list[ListItem]:
        """Get items in a list."""
        items = self._load_list(list_name)
        result = []

        for item in items:
            if include_completed or not item.get("completed", False):
                created = None
                if item.get("created"):
                    created = datetime.fromisoformat(item["created"])

                result.append(
                    ListItem(
                        id=item["id"],
                        text=item["text"],
                        completed=item.get("completed", False),
                        list_name=list_name,
                        created=created,
                    )
                )

        return result

    async def add_item(self, list_name: str, text: str) -> ListItem:
        """Add item to list. Creates list if needed."""
        items = self._load_list(list_name)

        now = datetime.now()
        new_item = {
            "id": str(uuid4()),
            "text": text,
            "completed": False,
            "created": now.isoformat(),
        }

        items.append(new_item)
        self._save_list(list_name, items)

        return ListItem(
            id=new_item["id"],
            text=text,
            completed=False,
            list_name=list_name,
            created=now,
        )

    async def complete_item(self, item_id: str) -> ListItem:
        """Mark item as complete."""
        # Search all lists for the item
        for list_name in await self.get_lists():
            items = self._load_list(list_name)

            for item in items:
                if item["id"] == item_id:
                    item["completed"] = True
                    self._save_list(list_name, items)

                    created = None
                    if item.get("created"):
                        created = datetime.fromisoformat(item["created"])

                    return ListItem(
                        id=item["id"],
                        text=item["text"],
                        completed=True,
                        list_name=list_name,
                        created=created,
                    )

        raise ValueError(f"Item not found: {item_id}")

    async def delete_item(self, item_id: str) -> bool:
        """Delete an item."""
        for list_name in await self.get_lists():
            items = self._load_list(list_name)
            original_len = len(items)
            items = [i for i in items if i["id"] != item_id]

            if len(items) < original_len:
                self._save_list(list_name, items)
                return True

        return False
