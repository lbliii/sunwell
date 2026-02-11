"""Entity extraction with dual-mode support (pattern/LLM).

Pattern-based extraction is the default (zero-cost, no LLM needed).
LLM-based extraction is opt-in for handling ambiguous cases.

Part of Phase 1: Foundation.
"""

import hashlib
import re
from typing import TYPE_CHECKING

from sunwell.memory.core.entities.types import (
    Entity,
    EntityMention,
    EntityType,
    ExtractionResult,
)

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


class PatternEntityExtractor:
    """Pattern-based entity extraction (zero-cost, no LLM).

    Uses regex patterns to extract common entities:
    - File paths: Anything in backticks or quotes that looks like a path
    - Tech terms: Capitalized words, acronyms, known frameworks
    - Code symbols: Class/function names
    - Concepts: Domain-specific terms

    This is fast, reliable, and works offline without any models.
    """

    # File path patterns
    FILE_PATTERNS = [
        re.compile(r"`([a-zA-Z0-9_/\-\.]+\.(py|js|ts|tsx|jsx|md|txt|json|yaml|yml|toml))`"),
        re.compile(r'"([a-zA-Z0-9_/\-\.]+\.(py|js|ts|tsx|jsx|md|txt|json|yaml|yml|toml))"'),
        re.compile(r"'([a-zA-Z0-9_/\-\.]+\.(py|js|ts|tsx|jsx|md|txt|json|yaml|yml|toml))'"),
        re.compile(r"`([a-zA-Z0-9_/\-\.]+/[a-zA-Z0-9_/\-\.]+)`"),  # Paths without extension
        re.compile(r"src/[a-zA-Z0-9_/\-\.]+"),
        re.compile(r"[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+\.[a-zA-Z]+"),
    ]

    # Technology patterns (known frameworks, libraries)
    TECH_KEYWORDS = {
        "Python", "JavaScript", "TypeScript", "React", "ReactJS", "Vue", "Angular",
        "Django", "Flask", "FastAPI", "Node", "NodeJS", "Express", "Next.js",
        "Docker", "Kubernetes", "Redis", "PostgreSQL", "MongoDB", "MySQL",
        "AWS", "GCP", "Azure", "Git", "GitHub", "GitLab",
        "pytest", "jest", "vitest", "unittest", "SQLAlchemy", "Pydantic",
        "numpy", "pandas", "scikit-learn", "tensorflow", "pytorch",
        "Svelte", "Solid", "Qwik", "Astro", "Remix",
    }

    # Code symbol patterns
    SYMBOL_PATTERNS = [
        re.compile(r"\b([A-Z][a-zA-Z0-9_]*)\("),  # Class instantiation
        re.compile(r"\bclass\s+([A-Z][a-zA-Z0-9_]*)\b"),  # Class definition
        re.compile(r"\bdef\s+([a-z_][a-zA-Z0-9_]*)\("),  # Function definition
        re.compile(r"\bfunction\s+([a-z_][a-zA-Z0-9_]*)\("),  # JS function
        re.compile(r"`([a-z_][a-zA-Z0-9_]*)\(`"),  # Function in backticks
    ]

    # Concept patterns (capitalized terms that look conceptual)
    CONCEPT_PATTERN = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
    )  # "Memory System", "Entity Graph"

    def extract(self, text: str, learning_id: str = "") -> ExtractionResult:
        """Extract entities from text using pattern matching.

        Args:
            text: Text to extract entities from
            learning_id: Optional learning ID for mentions

        Returns:
            ExtractionResult with extracted entities and mentions
        """
        entities: list[Entity] = []
        mentions: list[EntityMention] = []
        seen_names: set[str] = set()

        # Extract file paths
        for pattern in self.FILE_PATTERNS:
            for match in pattern.finditer(text):
                file_path = match.group(1) if match.lastindex else match.group(0)
                if file_path and file_path not in seen_names:
                    entity = self._create_entity(file_path, EntityType.FILE)
                    entities.append(entity)
                    if learning_id:
                        mentions.append(EntityMention(
                            learning_id=learning_id,
                            entity_id=entity.entity_id,
                            mention_text=file_path,
                            confidence=0.95,
                        ))
                    seen_names.add(file_path)

        # Extract tech keywords
        for tech in self.TECH_KEYWORDS:
            # Case-insensitive search
            pattern = re.compile(r"\b" + re.escape(tech) + r"\b", re.IGNORECASE)
            if pattern.search(text):
                if tech not in seen_names:
                    entity = self._create_entity(tech, EntityType.TECH)
                    entities.append(entity)
                    if learning_id:
                        mentions.append(EntityMention(
                            learning_id=learning_id,
                            entity_id=entity.entity_id,
                            mention_text=tech,
                            confidence=0.9,
                        ))
                    seen_names.add(tech)

        # Extract code symbols
        for pattern in self.SYMBOL_PATTERNS:
            for match in pattern.finditer(text):
                symbol = match.group(1)
                if symbol and symbol not in seen_names and not symbol.isupper():
                    # Avoid all-caps (likely acronyms, handled as TECH)
                    entity = self._create_entity(symbol, EntityType.SYMBOL)
                    entities.append(entity)
                    if learning_id:
                        mentions.append(EntityMention(
                            learning_id=learning_id,
                            entity_id=entity.entity_id,
                            mention_text=symbol,
                            confidence=0.85,
                        ))
                    seen_names.add(symbol)

        # Extract concepts (capitalized phrases)
        for match in self.CONCEPT_PATTERN.finditer(text):
            concept = match.group(1)
            # Filter out single-word concepts already captured
            if (
                concept
                and concept not in seen_names
                and concept not in self.TECH_KEYWORDS
                and len(concept) > 3
                and " " in concept  # Multi-word concepts only
            ):
                entity = self._create_entity(concept, EntityType.CONCEPT)
                entities.append(entity)
                if learning_id:
                    mentions.append(EntityMention(
                        learning_id=learning_id,
                        entity_id=entity.entity_id,
                        mention_text=concept,
                        confidence=0.7,
                    ))
                seen_names.add(concept)

        return ExtractionResult(
            entities=entities,
            mentions=mentions,
            extraction_mode="pattern",
            confidence=0.85,
        )

    def _create_entity(self, name: str, entity_type: EntityType) -> Entity:
        """Create an entity with ID and metadata."""
        # Generate stable ID from name + type
        entity_id = hashlib.sha256(
            f"{name.lower()}:{entity_type.value}".encode()
        ).hexdigest()[:16]

        return Entity(
            entity_id=entity_id,
            canonical_name=name,
            entity_type=entity_type,
            confidence=0.85,
        )


class LLMEntityExtractor:
    """LLM-based entity extraction (opt-in, for ambiguity).

    Uses an LLM to extract entities when patterns are insufficient.
    Falls back to pattern-based extraction if LLM is unavailable.

    This is more expensive but handles:
    - Ambiguous references
    - Context-dependent entities
    - Domain-specific terms not in patterns
    """

    def __init__(self, embedder: EmbeddingProtocol | None = None):
        """Initialize LLM extractor.

        Args:
            embedder: Optional embedder (if it has text generation capability)
        """
        self._embedder = embedder
        self._pattern_extractor = PatternEntityExtractor()

    async def extract(self, text: str, learning_id: str = "") -> ExtractionResult:
        """Extract entities using LLM.

        Args:
            text: Text to extract entities from
            learning_id: Optional learning ID for mentions

        Returns:
            ExtractionResult with extracted entities and mentions
        """
        # For now, fall back to pattern extraction
        # In a future iteration, this could use an LLM via embedder
        # if it supports text generation
        return self._pattern_extractor.extract(text, learning_id)


# Factory function for easy instantiation
def get_entity_extractor(
    mode: str = "pattern",
    embedder: EmbeddingProtocol | None = None,
) -> PatternEntityExtractor | LLMEntityExtractor:
    """Get an entity extractor.

    Args:
        mode: "pattern" (default) or "llm"
        embedder: Optional embedder for LLM mode

    Returns:
        Entity extractor instance
    """
    if mode == "llm" and embedder:
        return LLMEntityExtractor(embedder)
    return PatternEntityExtractor()
