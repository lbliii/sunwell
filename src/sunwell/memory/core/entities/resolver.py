"""Entity resolution and normalization.

Handles:
- String similarity matching (Levenshtein distance)
- User-defined alias mappings
- Canonical name resolution
- Duplicate entity detection

Part of Phase 1: Foundation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.memory.core.entities.types import Entity


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # j+1 instead of j since previous_row and current_row are one character longer
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class EntityResolver:
    """Resolves and normalizes entities to canonical forms.

    Uses multiple strategies:
    1. Exact match on aliases
    2. String similarity (Levenshtein < 3)
    3. User-defined alias mappings
    """

    def __init__(self, user_aliases: dict[str, str] | None = None):
        """Initialize resolver.

        Args:
            user_aliases: Optional user-defined alias mappings
                Example: {"React": "ReactJS", "py": "Python"}
        """
        self._user_aliases = user_aliases or {}
        self._entity_cache: dict[str, Entity] = {}

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the resolution cache.

        Args:
            entity: Entity to add
        """
        self._entity_cache[entity.entity_id] = entity

        # Also index by canonical name and aliases
        self._entity_cache[entity.canonical_name.lower()] = entity
        for alias in entity.aliases:
            self._entity_cache[alias.lower()] = entity

    def resolve(self, name: str, existing_entities: list[Entity]) -> Entity | None:
        """Resolve a name to an existing entity or None if novel.

        Args:
            name: Name to resolve
            existing_entities: List of known entities to match against

        Returns:
            Matching entity if found, None if this is a new entity
        """
        name_lower = name.lower()

        # 1. Check user-defined aliases first
        if name_lower in self._user_aliases:
            canonical = self._user_aliases[name_lower]
            for entity in existing_entities:
                if entity.canonical_name.lower() == canonical.lower():
                    return entity

        # 2. Exact match on canonical name or aliases
        for entity in existing_entities:
            if entity.canonical_name.lower() == name_lower:
                return entity
            if name_lower in (alias.lower() for alias in entity.aliases):
                return entity

        # 3. String similarity (Levenshtein < 3)
        for entity in existing_entities:
            # Only check similarity for same-length or close names
            if abs(len(entity.canonical_name) - len(name)) <= 2:
                distance = levenshtein_distance(
                    entity.canonical_name.lower(),
                    name_lower,
                )
                if distance <= 2:  # Allow up to 2 character edits
                    return entity

            # Check aliases too
            for alias in entity.aliases:
                if abs(len(alias) - len(name)) <= 2:
                    distance = levenshtein_distance(alias.lower(), name_lower)
                    if distance <= 2:
                        return entity

        # No match found - this is a new entity
        return None

    def merge_entities(self, entity1: Entity, entity2: Entity) -> Entity:
        """Merge two entities into one.

        Args:
            entity1: First entity (becomes canonical)
            entity2: Second entity (aliases added to first)

        Returns:
            Merged entity
        """
        # Use entity1 as canonical
        all_aliases = set(entity1.aliases)
        all_aliases.add(entity2.canonical_name)
        all_aliases.update(entity2.aliases)
        # Remove canonical name from aliases
        all_aliases.discard(entity1.canonical_name)

        return Entity(
            entity_id=entity1.entity_id,
            canonical_name=entity1.canonical_name,
            entity_type=entity1.entity_type,
            aliases=tuple(sorted(all_aliases)),
            first_seen=min(entity1.first_seen, entity2.first_seen),
            mention_count=entity1.mention_count + entity2.mention_count,
            confidence=max(entity1.confidence, entity2.confidence),
        )

    def normalize_name(self, name: str) -> str:
        """Normalize a name using user-defined aliases.

        Args:
            name: Name to normalize

        Returns:
            Canonical name if alias exists, otherwise original name
        """
        return self._user_aliases.get(name.lower(), name)


# Default alias mappings (can be overridden by user config)
DEFAULT_ALIASES = {
    "react": "ReactJS",
    "reactjs": "ReactJS",
    "react.js": "ReactJS",
    "py": "Python",
    "python3": "Python",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "node": "NodeJS",
    "nodejs": "NodeJS",
    "node.js": "NodeJS",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "redis": "Redis",
}
