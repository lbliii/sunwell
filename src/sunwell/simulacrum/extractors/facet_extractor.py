# src/sunwell/simulacrum/facet_extractor.py
"""Extract facets from content using heuristics and patterns.

Automatically detects:
- Diataxis type (tutorial, howto, reference, explanation)
- Target persona (novice, pragmatist, skeptic, expert)
- Domain tags (cli, api, config, security, testing)
- Confidence level from uncertainty markers

Part of RFC-014: Multi-Topology Memory.
"""


import re
from typing import TYPE_CHECKING

from sunwell.simulacrum.topology.facets import (
    ConfidenceLevel,
    ContentFacets,
    DiataxisType,
    PersonaType,
    VerificationState,
)

if TYPE_CHECKING:
    from sunwell.simulacrum.topology.structural import DocumentSection


class FacetExtractor:
    """Extract facets from content using heuristics and patterns."""

    # Diataxis detection patterns
    DIATAXIS_PATTERNS: dict[DiataxisType, list[str]] = {
        DiataxisType.TUTORIAL: [
            r'\blearn\b', r'\bstep[- ]by[- ]step\b', r'\bwalkthrough\b',
            r'\bfollow along\b', r'\blet\'s\b', r'\byou will\b',
        ],
        DiataxisType.HOWTO: [
            r'\bhow to\b', r'\bguide\b', r'\bsolve\b', r'\bachieve\b',
            r'\baccomplish\b', r'\btask\b', r'\bgoal\b',
        ],
        DiataxisType.REFERENCE: [
            r'\bapi\b', r'\bspecification\b', r'\bschema\b', r'\bformat\b',
            r'\boptions?\b', r'\bparameters?\b', r'\bsyntax\b',
        ],
        DiataxisType.EXPLANATION: [
            r'\bwhy\b', r'\barchitecture\b', r'\bdesign\b', r'\bconcept\b',
            r'\bunderstand\b', r'\btheory\b', r'\bbackground\b',
        ],
    }

    # Persona detection patterns
    PERSONA_PATTERNS: dict[PersonaType, list[str]] = {
        PersonaType.NOVICE: [
            r'\bbeginner\b', r'\bintroduction\b', r'\bbasic\b', r'\bfirst\b',
            r'\bsimple\b', r'\beasy\b', r'\bstarting\b',
        ],
        PersonaType.EXPERT: [
            r'\badvanced\b', r'\bexpert\b', r'\bprofessional\b', r'\bdeep dive\b',
            r'\barchitect\b', r'\boptimiz\b', r'\bperformance\b',
        ],
    }

    # Domain keywords
    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "cli": [r'\bcommand[- ]line\b', r'\bcli\b', r'\bterminal\b', r'\bshell\b'],
        "api": [r'\bapi\b', r'\bendpoint\b', r'\brequest\b', r'\bresponse\b'],
        "config": [r'\bconfig\b', r'\bsettings?\b', r'\byaml\b', r'\bjson\b', r'\btoml\b'],
        "security": [r'\bsecurity\b', r'\bauth\b', r'\btoken\b', r'\bpermission\b'],
        "testing": [r'\btest\b', r'\bpytest\b', r'\bassert\b', r'\bmock\b'],
    }

    def extract_from_text(
        self,
        text: str,
        section: DocumentSection | None = None,
        source_type: str = "docs",
    ) -> ContentFacets:
        """Extract facets from text content."""
        text_lower = text.lower()

        # Detect Diataxis type
        diataxis_type = self._detect_diataxis(text_lower, section)

        # Detect persona
        persona = self._detect_persona(text_lower)

        # Detect domains
        domains = self._detect_domains(text_lower)

        # Infer confidence from indicators
        confidence = self._infer_confidence(text_lower)

        return ContentFacets(
            diataxis_type=diataxis_type,
            primary_persona=persona,
            verification_state=VerificationState.UNVERIFIED,
            confidence=confidence,
            domain_tags=tuple(domains),
            source_type=source_type,
            source_authority=0.9 if source_type == "docs" else 0.7,
        )

    def _detect_diataxis(
        self,
        text: str,
        section: DocumentSection | None,
    ) -> DiataxisType | None:
        """Detect Diataxis type from text and section."""
        from sunwell.simulacrum.topology.structural import SectionType

        # Check section type first (high confidence)
        if section:
            type_mapping = {
                SectionType.TUTORIAL: DiataxisType.TUTORIAL,
                SectionType.QUICKSTART: DiataxisType.TUTORIAL,
                SectionType.HOWTO: DiataxisType.HOWTO,
                SectionType.TROUBLESHOOTING: DiataxisType.HOWTO,
                SectionType.REFERENCE: DiataxisType.REFERENCE,
                SectionType.API: DiataxisType.REFERENCE,
                SectionType.EXPLANATION: DiataxisType.EXPLANATION,
                SectionType.OVERVIEW: DiataxisType.EXPLANATION,
            }
            if section.section_type in type_mapping:
                return type_mapping[section.section_type]

        # Fall back to pattern matching
        scores: dict[DiataxisType, int] = {}
        for dtype, patterns in self.DIATAXIS_PATTERNS.items():
            scores[dtype] = sum(1 for p in patterns if re.search(p, text))

        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]

        return None

    def _detect_persona(self, text: str) -> PersonaType | None:
        """Detect target persona from text."""
        scores: dict[PersonaType, int] = {}
        for persona, patterns in self.PERSONA_PATTERNS.items():
            scores[persona] = sum(1 for p in patterns if re.search(p, text))

        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0]

        # Default to pragmatist if no clear signal
        return PersonaType.PRAGMATIST

    def _detect_domains(self, text: str) -> list[str]:
        """Detect domain tags from text."""
        domains = []
        for domain, patterns in self.DOMAIN_KEYWORDS.items():
            if any(re.search(p, text) for p in patterns):
                domains.append(domain)
        return domains

    def _infer_confidence(self, text: str) -> ConfidenceLevel:
        """Infer confidence level from uncertainty markers."""
        high_certainty = [
            r'\bmust\b', r'\balways\b', r'\bnever\b', r'\bdefinitely\b',
            r'\bguaranteed\b', r'\brequired\b',
        ]
        low_certainty = [
            r'\bmaybe\b', r'\bmight\b', r'\bpossibly\b', r'\bprobably\b',
            r'\btypically\b', r'\busually\b', r'\bgenerally\b',
        ]

        high_count = sum(1 for p in high_certainty if re.search(p, text))
        low_count = sum(1 for p in low_certainty if re.search(p, text))

        if high_count > low_count and high_count > 2:
            return ConfidenceLevel.HIGH
        elif low_count > high_count and low_count > 2:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MODERATE
