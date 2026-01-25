"""Sunwell Native Contacts Provider (RFC-078 Phase 4).

Local contact storage in .sunwell/contacts.json with vCard import support.
"""

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sunwell.models.providers.base import Contact, ContactsProvider

# Pre-compiled regex patterns for vCard parsing
_VCARD_SPLIT_RE = re.compile(r"(?=BEGIN:VCARD)")
_QUOTED_PRINTABLE_RE = re.compile(r"=([0-9A-Fa-f]{2})")


@lru_cache(maxsize=32)
def _get_vcard_field_pattern(field: str) -> re.Pattern[str]:
    """Get compiled regex pattern for a vCard field (cached)."""
    return re.compile(rf"^{field}[;:]([^\r\n]+)", re.MULTILINE | re.IGNORECASE)


class SunwellContacts(ContactsProvider):
    """Sunwell-native contacts stored in .sunwell/contacts.json."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize with data directory.

        Args:
            data_dir: The .sunwell data directory.
        """
        self.path = data_dir / "contacts.json"
        self._ensure_exists()

    def _ensure_exists(self) -> None:
        """Ensure the contacts file exists."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]")

    def _load(self) -> list[dict]:
        """Load contacts from JSON file."""
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, contacts: list[dict]) -> None:
        """Save contacts to JSON file."""
        self.path.write_text(json.dumps(contacts, default=str, indent=2))

    def _dict_to_contact(self, data: dict) -> Contact:
        """Convert dictionary to Contact."""
        birthday = data.get("birthday")
        if isinstance(birthday, str):
            try:
                birthday = datetime.fromisoformat(birthday)
            except ValueError:
                birthday = None

        created = data.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        modified = data.get("modified")
        if isinstance(modified, str):
            modified = datetime.fromisoformat(modified)

        return Contact(
            id=data["id"],
            name=data["name"],
            email=data.get("email"),
            phone=data.get("phone"),
            organization=data.get("organization"),
            title=data.get("title"),
            notes=data.get("notes"),
            tags=tuple(data.get("tags", [])),
            birthday=birthday,
            created=created,
            modified=modified,
        )

    async def list_contacts(self, limit: int = 100) -> list[Contact]:
        """List all contacts."""
        data = self._load()
        contacts = [self._dict_to_contact(c) for c in data]

        # Sort by name
        contacts.sort(key=lambda c: c.name.lower())
        return contacts[:limit]

    async def get_contact(self, contact_id: str) -> Contact | None:
        """Get a specific contact by ID."""
        data = self._load()
        for c in data:
            if c["id"] == contact_id:
                return self._dict_to_contact(c)
        return None

    async def search(self, query: str, limit: int = 20) -> list[Contact]:
        """Search contacts by name, email, or organization."""
        query_lower = query.lower()
        data = self._load()
        matching: list[Contact] = []

        for c in data:
            name = c.get("name", "").lower()
            email = c.get("email", "").lower() if c.get("email") else ""
            org = c.get("organization", "").lower() if c.get("organization") else ""
            notes = c.get("notes", "").lower() if c.get("notes") else ""

            if (
                query_lower in name
                or query_lower in email
                or query_lower in org
                or query_lower in notes
            ):
                matching.append(self._dict_to_contact(c))

            if len(matching) >= limit:
                break

        return matching

    async def get_by_tag(self, tag: str) -> list[Contact]:
        """Get contacts with a specific tag."""
        tag_lower = tag.lower()
        data = self._load()
        matching: list[Contact] = []

        for c in data:
            tags = [t.lower() for t in c.get("tags", [])]
            if tag_lower in tags:
                matching.append(self._dict_to_contact(c))

        return matching

    async def create_contact(
        self,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        organization: str | None = None,
        tags: list[str] | None = None,
    ) -> Contact:
        """Create a new contact."""
        data = self._load()
        now = datetime.now()

        new_contact = {
            "id": str(uuid4()),
            "name": name,
            "email": email,
            "phone": phone,
            "organization": organization,
            "title": None,
            "notes": None,
            "tags": tags or [],
            "birthday": None,
            "created": now.isoformat(),
            "modified": now.isoformat(),
        }

        data.append(new_contact)
        self._save(data)
        return self._dict_to_contact(new_contact)

    async def update_contact(self, contact: Contact) -> Contact:
        """Update an existing contact."""
        data = self._load()
        now = datetime.now()

        for i, c in enumerate(data):
            if c["id"] == contact.id:
                data[i] = {
                    "id": contact.id,
                    "name": contact.name,
                    "email": contact.email,
                    "phone": contact.phone,
                    "organization": contact.organization,
                    "title": contact.title,
                    "notes": contact.notes,
                    "tags": list(contact.tags),
                    "birthday": contact.birthday.isoformat() if contact.birthday else None,
                    "created": contact.created.isoformat() if contact.created else None,
                    "modified": now.isoformat(),
                }
                self._save(data)
                return self._dict_to_contact(data[i])

        # Contact not found, create new
        return await self.create_contact(
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            organization=contact.organization,
            tags=list(contact.tags),
        )

    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact."""
        data = self._load()
        original_len = len(data)
        data = [c for c in data if c["id"] != contact_id]
        self._save(data)
        return len(data) < original_len

    async def get_all_tags(self) -> list[str]:
        """Get all unique tags."""
        data = self._load()
        tags: set[str] = set()
        for c in data:
            tags.update(c.get("tags", []))
        return sorted(tags)

    async def import_vcard(self, vcard_path: Path) -> int:
        """Import contacts from a vCard file (.vcf).

        Args:
            vcard_path: Path to vCard file.

        Returns:
            Number of contacts imported.
        """
        if not vcard_path.exists():
            return 0

        content = vcard_path.read_text(encoding="utf-8", errors="replace")
        return await self._parse_vcard(content)

    async def _parse_vcard(self, content: str) -> int:
        """Parse vCard content and import contacts."""
        # Split into individual vCards
        vcards = _VCARD_SPLIT_RE.split(content)
        data = self._load()  # Load once at start
        now = datetime.now()
        imported = 0

        for vcard in vcards:
            if not vcard.strip() or "BEGIN:VCARD" not in vcard:
                continue

            # Parse fields
            name = self._extract_vcard_field(vcard, "FN")
            if not name:
                # Try N field (structured name)
                n_field = self._extract_vcard_field(vcard, "N")
                if n_field:
                    parts = n_field.split(";")
                    # N format: LastName;FirstName;MiddleName;Prefix;Suffix
                    name = f"{parts[1]} {parts[0]}".strip() if len(parts) >= 2 else n_field

            if not name:
                continue

            email = self._extract_vcard_field(vcard, "EMAIL")
            phone = self._extract_vcard_field(vcard, "TEL")
            org = self._extract_vcard_field(vcard, "ORG")
            title = self._extract_vcard_field(vcard, "TITLE")
            note = self._extract_vcard_field(vcard, "NOTE")

            # Parse birthday
            bday_str = self._extract_vcard_field(vcard, "BDAY")
            birthday = None
            if bday_str:
                try:
                    # Try common formats
                    for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"]:
                        try:
                            birthday = datetime.strptime(bday_str[:len(fmt.replace("%", ""))], fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            new_contact = {
                "id": str(uuid4()),
                "name": name,
                "email": email,
                "phone": phone,
                "organization": org.split(";")[0] if org else None,  # ORG can have multiple parts
                "title": title,
                "notes": note,
                "tags": ["imported"],
                "birthday": birthday.isoformat() if birthday else None,
                "created": now.isoformat(),
                "modified": now.isoformat(),
            }

            data.append(new_contact)
            imported += 1

        if imported > 0:
            self._save(data)  # Save once at end

        return imported

    def _extract_vcard_field(self, vcard: str, field: str) -> str | None:
        """Extract a field value from vCard content."""
        # Handle various vCard field formats:
        # FIELD:value
        # FIELD;TYPE=type:value
        # FIELD;CHARSET=UTF-8:value
        match = _get_vcard_field_pattern(field).search(vcard)

        if not match:
            return None

        value = match.group(1)

        # If there's a type prefix (e.g., "TYPE=WORK:email@example.com")
        if ":" in value:
            value = value.split(":", 1)[-1]

        # Handle quoted-printable encoding
        if "ENCODING=QUOTED-PRINTABLE" in match.group(0).upper():
            value = self._decode_quoted_printable(value)

        return value.strip() if value else None

    def _decode_quoted_printable(self, text: str) -> str:
        """Decode quoted-printable encoded text."""
        # Handle soft line breaks
        text = text.replace("=\n", "").replace("=\r\n", "")

        # Decode hex values
        def decode_hex(match: re.Match[str]) -> str:
            return chr(int(match.group(1), 16))

        return _QUOTED_PRINTABLE_RE.sub(decode_hex, text)

    async def export_vcard(self, contact_ids: list[str] | None = None) -> str:
        """Export contacts to vCard format.

        Args:
            contact_ids: Specific contacts to export, or None for all.

        Returns:
            vCard formatted string.
        """
        data = self._load()

        if contact_ids:
            data = [c for c in data if c["id"] in contact_ids]

        vcards: list[str] = []

        for c in data:
            lines = [
                "BEGIN:VCARD",
                "VERSION:3.0",
                f"FN:{c['name']}",
            ]

            if c.get("email"):
                lines.append(f"EMAIL:{c['email']}")
            if c.get("phone"):
                lines.append(f"TEL:{c['phone']}")
            if c.get("organization"):
                lines.append(f"ORG:{c['organization']}")
            if c.get("title"):
                lines.append(f"TITLE:{c['title']}")
            if c.get("notes"):
                # Escape newlines in notes
                notes = c["notes"].replace("\n", "\\n")
                lines.append(f"NOTE:{notes}")
            if c.get("birthday"):
                bday = datetime.fromisoformat(c["birthday"])
                lines.append(f"BDAY:{bday.strftime('%Y-%m-%d')}")

            lines.append("END:VCARD")
            vcards.append("\r\n".join(lines))

        return "\r\n".join(vcards)
