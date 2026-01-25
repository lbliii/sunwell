# src/sunwell/simulacrum/topology_extractor.py
"""Extract concept relationships from content.

Supports:
- LLM-based relationship extraction (accurate but expensive)
- Heuristic-based extraction (fast, lower accuracy)

Part of RFC-014: Multi-Topology Memory.
RFC-084: Enhanced with Jaccard similarity for RELATES_TO detection.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING, Pattern

from sunwell.memory.simulacrum.topology.topology_base import ConceptEdge, RelationType

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol


# =============================================================================
# Pre-compiled patterns for relationship detection
# Compiled once at module load, avoiding per-call regex compilation overhead.
# =============================================================================

_ELABORATION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"(?:specifically|in particular|for example)", re.IGNORECASE),
    re.compile(r"(?:this means|in other words|that is)", re.IGNORECASE),
    re.compile(r"(?:to clarify|more precisely)", re.IGNORECASE),
    re.compile(r"(?:expanding on|to elaborate|in detail)", re.IGNORECASE),
)

_CONTRADICTION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"(?:actually|however|but|instead)", re.IGNORECASE),
    re.compile(r"(?:not|never|don't|doesn't|won't)", re.IGNORECASE),
    re.compile(r"(?:wrong|incorrect|false|mistake)", re.IGNORECASE),
    re.compile(r"(?:in contrast|unlike|contrary to)", re.IGNORECASE),
)

_DEPENDENCY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\brequires?\b", re.IGNORECASE),
    re.compile(r"\bdepends? on\b", re.IGNORECASE),
    re.compile(r"\bbuilding on\b", re.IGNORECASE),
    re.compile(r"\bneeds?\b.*\bfirst\b", re.IGNORECASE),
    re.compile(r"\bprerequisite\b", re.IGNORECASE),
)

_SUMMARY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bin summary\b", re.IGNORECASE),
    re.compile(r"\bto summarize\b", re.IGNORECASE),
    re.compile(r"\bin short\b", re.IGNORECASE),
    re.compile(r"\boverall\b", re.IGNORECASE),
    re.compile(r"\bin conclusion\b", re.IGNORECASE),
)


class TopologyExtractor:
    """Extract concept relationships from content using LLM or heuristics.

    RFC-084: Enhanced with automatic Jaccard similarity for RELATES_TO edges.
    """

    # Minimum Jaccard similarity threshold for RELATES_TO relationships
    RELATES_TO_THRESHOLD: float = 0.3

    def __init__(self, model: ModelProtocol | None = None):
        self.model = model

    async def extract_relationships(
        self,
        source_id: str,
        source_text: str,
        candidate_ids: list[str],
        candidate_texts: list[str],
    ) -> list[ConceptEdge]:
        """Identify relationships between a source and candidate chunks.

        Uses LLM to detect: elaboration, contradiction, dependency, etc.
        """
        if not self.model or not candidate_ids:
            return []

        # Format candidates
        candidates_formatted = "\n\n".join(
            f"[{cid}]: {text[:500]}"
            for cid, text in zip(candidate_ids, candidate_texts, strict=False)
        )

        prompt = f"""Analyze relationships between the SOURCE chunk and CANDIDATE chunks.

SOURCE [{source_id}]:
{source_text[:1000]}

CANDIDATES:
{candidates_formatted}

For each meaningful relationship, output one line in format:
RELATION_TYPE: [candidate_id] - brief reason

Valid RELATION_TYPEs:
- ELABORATES: Source provides more detail about candidate
- SUMMARIZES: Source summarizes candidate
- CONTRADICTS: Source conflicts with candidate
- SUPPORTS: Source provides evidence for candidate
- DEPENDS_ON: Source requires candidate to be understood
- SUPERSEDES: Source replaces/updates candidate
- RELATES_TO: Source is topically related to candidate

Only output strong, clear relationships. Skip weak or uncertain ones.

Relationships:"""

        result = await self.model.generate(prompt)

        # Parse response
        edges = []
        timestamp = datetime.now().isoformat()

        for line in result.text.strip().split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue

            try:
                relation_part, rest = line.split(":", 1)
                relation_type = RelationType(relation_part.strip().lower())

                # Extract candidate ID (in brackets)
                match = re.search(r'\[([^\]]+)\]', rest)
                if match:
                    target_id = match.group(1)
                    reason = rest.replace(f"[{target_id}]", "").strip(" -")

                    if target_id in candidate_ids:
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation=relation_type,
                            confidence=0.8,  # LLM-extracted, needs confirmation
                            evidence=reason,
                            auto_extracted=True,
                            timestamp=timestamp,
                        ))
            except (ValueError, KeyError):
                continue  # Skip malformed lines

        return edges

    def extract_heuristic_relationships(
        self,
        source_id: str,
        source_text: str,
        candidate_ids: list[str],
        candidate_texts: list[str],
    ) -> list[ConceptEdge]:
        """Heuristic relationship detection without LLM.

        RFC-084: Enhanced with Jaccard similarity for RELATES_TO.

        Detects:
        - RELATES_TO: Jaccard similarity > threshold (default 0.3)
        - CONTRADICTS: Contradiction signals + topic overlap
        - DEPENDS_ON: Dependency signals + topic overlap
        - ELABORATES: Elaboration signals + topic overlap
        - SUMMARIZES: Summary signals + topic overlap
        """
        edges: list[ConceptEdge] = []
        timestamp = datetime.now().isoformat()

        source_lower = source_text.lower()
        source_words = self._tokenize(source_text)

        for cid, ctext in zip(candidate_ids, candidate_texts, strict=True):
            candidate_words = self._tokenize(ctext)

            # RFC-084: Jaccard similarity for RELATES_TO
            similarity = self._jaccard_similarity(source_words, candidate_words)
            if similarity > self.RELATES_TO_THRESHOLD:
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.RELATES_TO,
                    confidence=similarity,
                    evidence=f"Jaccard similarity: {similarity:.2f}",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

            # Check for explicit reference (stronger signal)
            if cid.lower() in source_lower:
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.RELATES_TO,
                    confidence=0.9,
                    evidence=f"Explicit reference to {cid}",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

            # Check for elaboration patterns (check first - more specific)
            if self._is_elaboration(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.ELABORATES,
                    confidence=0.7,
                    evidence="Elaboration pattern detected",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

            # Check for contradiction patterns
            if self._is_contradiction(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.CONTRADICTS,
                    confidence=0.8,
                    evidence="Contradiction pattern detected",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

            # Check for dependency signals
            if self._is_dependency(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.DEPENDS_ON,
                    confidence=0.6,
                    evidence="Dependency pattern detected",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

            # Check for summary signals
            if self._is_summary(source_text, ctext):
                edges.append(ConceptEdge(
                    source_id=source_id,
                    target_id=cid,
                    relation=RelationType.SUMMARIZES,
                    confidence=0.6,
                    evidence="Summary pattern detected",
                    auto_extracted=True,
                    timestamp=timestamp,
                ))

        return edges

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercased words, filtering short tokens."""
        return {w.lower() for w in text.split() if len(w) > 2}

    def _jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Calculate Jaccard similarity coefficient."""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _is_elaboration(self, source: str, target: str) -> bool:
        """Check if source elaborates on target."""
        source_lower = source.lower()
        has_signal = any(p.search(source_lower) for p in _ELABORATION_PATTERNS)
        if not has_signal:
            return False
        # Check topic overlap
        return self._jaccard_similarity(
            self._tokenize(source), self._tokenize(target)
        ) > 0.15

    def _is_contradiction(self, source: str, target: str) -> bool:
        """Check if source contradicts target."""
        source_lower = source.lower()
        has_signal = any(p.search(source_lower) for p in _CONTRADICTION_PATTERNS)
        if not has_signal:
            return False
        # Check topic overlap
        return self._jaccard_similarity(
            self._tokenize(source), self._tokenize(target)
        ) > 0.15

    def _is_dependency(self, source: str, target: str) -> bool:
        """Check if source depends on target."""
        source_lower = source.lower()
        has_signal = any(p.search(source_lower) for p in _DEPENDENCY_PATTERNS)
        if not has_signal:
            return False
        return self._jaccard_similarity(
            self._tokenize(source), self._tokenize(target)
        ) > 0.1

    def _is_summary(self, source: str, target: str) -> bool:
        """Check if source summarizes target."""
        source_lower = source.lower()
        has_signal = any(p.search(source_lower) for p in _SUMMARY_PATTERNS)
        if not has_signal:
            return False
        return self._jaccard_similarity(
            self._tokenize(source), self._tokenize(target)
        ) > 0.1
