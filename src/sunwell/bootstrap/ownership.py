"""Ownership Map — RFC-050.

Track code ownership derived from git history.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sunwell.bootstrap.types import BlameRegion


@dataclass(frozen=True, slots=True)
class OwnershipDomain:
    """A domain of code ownership."""

    name: str
    """Domain name (usually directory or module)."""

    primary_owner: str
    """Git author who owns most of this code."""

    ownership_percentage: float
    """What percentage of code primary_owner wrote."""

    files: tuple[Path, ...]
    """Files in this domain."""

    secondary_owners: tuple[str, ...]
    """Other significant contributors."""


class OwnershipMap:
    """Track code ownership derived from git history."""

    def __init__(self, path: Path):
        """Initialize ownership map.

        Args:
            path: Directory to store ownership data
        """
        self._path = Path(path) / "ownership.json"
        self._domains: dict[str, OwnershipDomain] = {}
        self._load()

    def _load(self) -> None:
        """Load ownership data from disk."""
        if not self._path.exists():
            return

        try:
            with open(self._path) as f:
                data = json.load(f)

            for name, domain_data in data.get("domains", {}).items():
                self._domains[name] = OwnershipDomain(
                    name=domain_data["name"],
                    primary_owner=domain_data["primary_owner"],
                    ownership_percentage=domain_data["ownership_percentage"],
                    files=tuple(Path(f) for f in domain_data["files"]),
                    secondary_owners=tuple(domain_data["secondary_owners"]),
                )
        except (json.JSONDecodeError, OSError, KeyError):
            self._domains = {}

    def _save(self) -> None:
        """Save ownership data to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "domains": {
                name: {
                    "name": domain.name,
                    "primary_owner": domain.primary_owner,
                    "ownership_percentage": domain.ownership_percentage,
                    "files": [str(f) for f in domain.files],
                    "secondary_owners": list(domain.secondary_owners),
                }
                for name, domain in self._domains.items()
            }
        }

        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    async def populate(self, domains: dict[str, OwnershipDomain]) -> None:
        """Populate ownership from bootstrap.

        Args:
            domains: Domain name → OwnershipDomain mapping
        """
        self._domains = domains
        self._save()

    def populate_from_blame(
        self,
        blame_map: dict[Path, list[BlameRegion]],
    ) -> dict[str, OwnershipDomain]:
        """Infer ownership domains from git blame data.

        Strategy:
        1. Cluster files by directory
        2. For each directory, find primary contributor (>50% blame)
        3. Create ownership domain with primary + secondary owners

        Args:
            blame_map: File → blame regions mapping

        Returns:
            Domain name → OwnershipDomain mapping
        """
        domains: dict[str, OwnershipDomain] = {}

        # Group files by directory
        dir_to_files: dict[str, list[Path]] = {}
        for file_path in blame_map:
            dir_name = file_path.parent.name or "root"
            dir_to_files.setdefault(dir_name, []).append(file_path)

        # For each directory, find primary contributor
        for dir_name, files in dir_to_files.items():
            author_lines: dict[str, int] = {}

            for file_path in files:
                if file_path not in blame_map:
                    continue
                for region in blame_map[file_path]:
                    lines = region.end_line - region.start_line + 1
                    author_lines[region.author] = author_lines.get(region.author, 0) + lines

            if not author_lines:
                continue

            total_lines = sum(author_lines.values())
            primary_author = max(author_lines, key=lambda a: author_lines[a])

            # Get secondary owners (contributors with >10% of lines)
            threshold = total_lines * 0.10
            secondary = [
                a for a in author_lines
                if a != primary_author and author_lines[a] >= threshold
            ]

            domains[dir_name] = OwnershipDomain(
                name=dir_name,
                primary_owner=primary_author,
                ownership_percentage=author_lines[primary_author] / total_lines,
                files=tuple(files),
                secondary_owners=tuple(secondary[:3]),  # Top 3 secondary
            )

        self._domains = domains
        self._save()
        return domains

    def get_owner(self, file: Path) -> str | None:
        """Get the likely owner of a file.

        Args:
            file: File path

        Returns:
            Primary owner's name or None if unknown
        """
        # Find the domain containing this file
        for domain in self._domains.values():
            if file in domain.files:
                return domain.primary_owner

        # Try directory match
        dir_name = file.parent.name
        if dir_name in self._domains:
            return self._domains[dir_name].primary_owner

        return None

    def get_experts(self, file: Path) -> list[str]:
        """Get experts for a file (owner + secondary).

        Args:
            file: File path

        Returns:
            List of expert names (primary owner first)
        """
        for domain in self._domains.values():
            if file in domain.files:
                return [domain.primary_owner, *domain.secondary_owners]

        # Try directory match
        dir_name = file.parent.name
        if dir_name in self._domains:
            domain = self._domains[dir_name]
            return [domain.primary_owner, *domain.secondary_owners]

        return []

    def suggest_reviewer(self, changed_files: list[Path]) -> str | None:
        """Suggest a reviewer for a set of changes.

        Args:
            changed_files: List of changed file paths

        Returns:
            Suggested reviewer's name or None
        """
        owners = [self.get_owner(f) for f in changed_files]
        owners = [o for o in owners if o]

        if not owners:
            return None

        # Most common owner among changed files
        return Counter(owners).most_common(1)[0][0]

    def get_domain(self, name: str) -> OwnershipDomain | None:
        """Get a specific ownership domain.

        Args:
            name: Domain name

        Returns:
            OwnershipDomain or None
        """
        return self._domains.get(name)

    def get_all_domains(self) -> list[OwnershipDomain]:
        """Get all ownership domains.

        Returns:
            List of all domains
        """
        return list(self._domains.values())

    def domain_count(self) -> int:
        """Get number of ownership domains.

        Returns:
            Number of domains
        """
        return len(self._domains)
