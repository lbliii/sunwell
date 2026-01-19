"""Lens Discovery for Expertise-Aware Planning (RFC-039).

Finds and loads lenses that match a detected domain.
Supports multiple lens sources including local files and external rules.

Example:
    >>> discovery = LensDiscovery()
    >>> lenses = await discovery.discover("documentation")
    >>> len(lenses)
    2
    >>> [l.metadata.name for l in lenses]
    ['Technical Writer', 'Team Writer']
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.lens import Lens

from sunwell.naaru.expertise.classifier import Domain


class LensSource(Enum):
    """Types of lens sources."""

    LOCAL = "local"  # Local .lens files
    DORI = "dori"  # DORI rules (Cursor rules)
    FOUNT = "fount"  # Fount registry (future)


# Domain to lens mapping
# Lists lens file names (without path) for each domain
DOMAIN_LENS_MAP: dict[Domain, list[str]] = {
    Domain.DOCUMENTATION: [
        "tech-writer.lens",
        "team-writer.lens",
    ],
    Domain.CODE: [
        "coder.lens",
        "team-dev.lens",
    ],
    Domain.REVIEW: [
        "code-reviewer.lens",
        "team-qa.lens",
    ],
    Domain.TEST: [
        "coder.lens",  # Coder lens has testing heuristics
        "team-qa.lens",
    ],
    Domain.REFACTOR: [
        "code-reviewer.lens",
        "coder.lens",
    ],
    Domain.PROJECT: [
        "team-dev.lens",
        "team-pm.lens",
    ],
    Domain.GENERAL: [
        "helper.lens",
    ],
}

# DORI rule paths for domains (relative to cursor rules root)
DORI_RULE_MAP: dict[Domain, list[str]] = {
    Domain.DOCUMENTATION: [
        "modules/diataxis-framework",
        "modules/docs-quality-principles",
        "utilities/docs-style-guide",
        "validation/docs-audit",
    ],
}

# Default lens search paths
DEFAULT_SEARCH_PATHS = [
    Path.cwd() / "lenses",
    Path.home() / ".sunwell" / "lenses",
]

# Default DORI rules paths
DEFAULT_DORI_PATHS = [
    Path.home() / ".cursor" / "rules",
    Path.cwd() / ".cursor" / "rules",
]


@dataclass
class LensDiscovery:
    """Discover and load lenses for a domain.

    Searches configured paths for lens files matching the domain,
    and optionally loads DORI rules as supplementary expertise.

    Example:
        >>> discovery = LensDiscovery()
        >>> lenses = await discovery.discover("documentation")
    """

    # Paths to search for .lens files
    search_paths: list[Path] = field(default_factory=lambda: list(DEFAULT_SEARCH_PATHS))

    # Paths to search for DORI rules
    dori_paths: list[Path] = field(default_factory=lambda: list(DEFAULT_DORI_PATHS))

    # Whether to include DORI rules
    include_dori: bool = True

    # Cache for loaded lenses
    _lens_cache: dict[str, Lens] = field(default_factory=dict, init=False)

    async def discover(
        self,
        domain: Domain | str,
        max_lenses: int = 3,
    ) -> list[Lens]:
        """Discover lenses for a domain.

        Args:
            domain: Domain enum or string name
            max_lenses: Maximum number of lenses to return

        Returns:
            List of loaded Lens objects
        """
        # Normalize domain
        if isinstance(domain, str):
            try:
                domain = Domain(domain)
            except ValueError:
                domain = Domain.GENERAL

        lenses: list[Lens] = []

        # Get lens names for domain
        lens_names = DOMAIN_LENS_MAP.get(domain, [])

        # Search for matching lens files
        for lens_name in lens_names:
            if len(lenses) >= max_lenses:
                break

            lens = await self._find_and_load_lens(lens_name)
            if lens:
                lenses.append(lens)

        return lenses

    async def discover_all_for_domain(
        self,
        domain: Domain | str,
    ) -> tuple[list[Lens], list[Path]]:
        """Discover all expertise sources for a domain.

        Returns both lens objects and DORI rule paths.

        Args:
            domain: Domain enum or string name

        Returns:
            Tuple of (lenses, dori_rule_paths)
        """
        # Normalize domain
        if isinstance(domain, str):
            try:
                domain = Domain(domain)
            except ValueError:
                domain = Domain.GENERAL

        # Discover lenses
        lenses = await self.discover(domain, max_lenses=10)

        # Find DORI rules
        dori_paths: list[Path] = []
        if self.include_dori:
            dori_paths = self._find_dori_rules(domain)

        return (lenses, dori_paths)

    async def _find_and_load_lens(self, lens_name: str) -> Lens | None:
        """Find and load a lens by name.

        Searches configured paths and returns loaded lens if found.
        """
        # Check cache
        if lens_name in self._lens_cache:
            return self._lens_cache[lens_name]

        # Search paths
        for search_path in self.search_paths:
            lens_path = search_path / lens_name
            if lens_path.exists():
                lens = await self._load_lens(lens_path)
                if lens:
                    self._lens_cache[lens_name] = lens
                    return lens

        return None

    async def _load_lens(self, path: Path) -> Lens | None:
        """Load a lens from a file path.

        Uses the schema loader for proper parsing.
        """
        try:
            from sunwell.core.types import LensReference
            from sunwell.fount.client import FountClient
            from sunwell.fount.resolver import LensResolver
            from sunwell.schema.loader import LensLoader

            # Create loader chain
            fount = FountClient()
            loader = LensLoader(fount_client=fount)
            resolver = LensResolver(loader=loader)

            # Resolve lens
            source = str(path)
            if not source.startswith("/"):
                source = f"./{source}"

            ref = LensReference(source=source)
            lens = await resolver.resolve(ref)

            return lens

        except Exception:
            # Silently skip invalid lenses
            return None

    def _find_dori_rules(self, domain: Domain) -> list[Path]:
        """Find DORI rule paths for a domain.

        Returns list of paths to DORI rule directories/files.
        """
        rule_names = DORI_RULE_MAP.get(domain, [])
        found_paths: list[Path] = []

        for rule_name in rule_names:
            for dori_root in self.dori_paths:
                # Check for directory with RULE.mdc
                rule_dir = dori_root / rule_name
                if rule_dir.exists():
                    rule_file = rule_dir / "RULE.mdc"
                    if rule_file.exists():
                        found_paths.append(rule_file)
                    elif rule_dir.is_dir():
                        # Look for any .mdc file
                        mdc_files = list(rule_dir.glob("*.mdc"))
                        found_paths.extend(mdc_files[:1])  # Take first

        return found_paths

    def add_search_path(self, path: Path) -> None:
        """Add a lens search path.

        Args:
            path: Directory to search for .lens files
        """
        if path not in self.search_paths:
            self.search_paths.append(path)

    def add_dori_path(self, path: Path) -> None:
        """Add a DORI rules path.

        Args:
            path: Directory containing DORI rules
        """
        if path not in self.dori_paths:
            self.dori_paths.append(path)


# Convenience function for quick discovery
async def discover_lenses(domain: str | Domain) -> list[Lens]:
    """Discover lenses for a domain.

    Convenience function using default LensDiscovery.

    Args:
        domain: Domain name or enum

    Returns:
        List of loaded Lens objects
    """
    discovery = LensDiscovery()
    return await discovery.discover(domain)
