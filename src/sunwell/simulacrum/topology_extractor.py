# src/sunwell/simulacrum/topology_extractor.py
"""Extract concept relationships from content.

Supports:
- LLM-based relationship extraction (accurate but expensive)
- Heuristic-based extraction (fast, lower accuracy)

Part of RFC-014: Multi-Topology Memory.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from sunwell.simulacrum.topology import RelationType, ConceptEdge

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


class TopologyExtractor:
    """Extract concept relationships from content using LLM or heuristics."""
    
    def __init__(self, model: "ModelProtocol | None" = None):
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
            for cid, text in zip(candidate_ids, candidate_texts)
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
        
        Detects:
        - Explicit references ("as mentioned in", "see also", "cf.")
        - Contradiction signals ("however", "but", "unlike", "in contrast")
        - Dependency signals ("requires", "depends on", "building on")
        """
        edges = []
        timestamp = datetime.now().isoformat()
        
        source_lower = source_text.lower()
        
        for cid, ctext in zip(candidate_ids, candidate_texts):
            # Check for explicit reference
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
            
            # Check for contradiction signals near candidate mentions
            contradiction_patterns = [
                r'\bhowever\b',
                r'\bbut\b',
                r'\bunlike\b',
                r'\bin contrast\b',
                r'\bcontradicts?\b',
            ]
            for pattern in contradiction_patterns:
                if re.search(pattern, source_lower):
                    # Check if candidate topic is nearby
                    candidate_keywords = set(ctext.lower().split()[:10])
                    source_words = set(source_lower.split())
                    overlap = len(candidate_keywords & source_words)
                    if overlap > 3:  # Significant topic overlap
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=cid,
                            relation=RelationType.CONTRADICTS,
                            confidence=0.5,  # Low confidence, needs review
                            evidence="Contradiction signal + topic overlap",
                            auto_extracted=True,
                            timestamp=timestamp,
                        ))
                        break
            
            # Check for dependency signals
            dependency_patterns = [
                r'\brequires?\b',
                r'\bdepends? on\b',
                r'\bbuilding on\b',
                r'\bneeds?\b.*\bfirst\b',
            ]
            for pattern in dependency_patterns:
                if re.search(pattern, source_lower):
                    # Check if this relates to candidate
                    candidate_keywords = set(ctext.lower().split()[:10])
                    source_words = set(source_lower.split())
                    overlap = len(candidate_keywords & source_words)
                    if overlap > 2:
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=cid,
                            relation=RelationType.DEPENDS_ON,
                            confidence=0.6,
                            evidence="Dependency signal + topic overlap",
                            auto_extracted=True,
                            timestamp=timestamp,
                        ))
                        break
            
            # Check for elaboration signals
            elaboration_patterns = [
                r'\bspecifically\b',
                r'\bin detail\b',
                r'\bmore precisely\b',
                r'\bto elaborate\b',
                r'\bexpanding on\b',
            ]
            for pattern in elaboration_patterns:
                if re.search(pattern, source_lower):
                    candidate_keywords = set(ctext.lower().split()[:10])
                    source_words = set(source_lower.split())
                    overlap = len(candidate_keywords & source_words)
                    if overlap > 2:
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=cid,
                            relation=RelationType.ELABORATES,
                            confidence=0.6,
                            evidence="Elaboration signal + topic overlap",
                            auto_extracted=True,
                            timestamp=timestamp,
                        ))
                        break
            
            # Check for summary signals
            summary_patterns = [
                r'\bin summary\b',
                r'\bto summarize\b',
                r'\bin short\b',
                r'\boverall\b',
            ]
            for pattern in summary_patterns:
                if re.search(pattern, source_lower):
                    candidate_keywords = set(ctext.lower().split()[:10])
                    source_words = set(source_lower.split())
                    overlap = len(candidate_keywords & source_words)
                    if overlap > 2:
                        edges.append(ConceptEdge(
                            source_id=source_id,
                            target_id=cid,
                            relation=RelationType.SUMMARIZES,
                            confidence=0.6,
                            evidence="Summary signal + topic overlap",
                            auto_extracted=True,
                            timestamp=timestamp,
                        ))
                        break
        
        return edges
