# src/sunwell/simulacrum/facet_extractor.py
"""Extract facets from content using heuristics and pre-compiled patterns.

Automatically detects:
- Diataxis type (tutorial, howto, reference, explanation)
- Target persona (novice, pragmatist, skeptic, expert)
- Domain tags (cli, api, config, security, testing)
- Confidence level from uncertainty markers

Part of RFC-014: Multi-Topology Memory.

Note: Refactored from class to module-level functions (the class was stateless).
Patterns are pre-compiled at module load time for O(1) matching.
"""

import re
from re import Pattern
from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.topology.facets import (
    ConfidenceLevel,
    ContentFacets,
    DiataxisType,
    PersonaType,
    VerificationState,
)

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.topology.structural import DocumentSection


# =============================================================================
# Pre-compiled patterns for facet extraction
# Compiled once at module load, avoiding per-call regex compilation overhead.
# =============================================================================

_DIATAXIS_PATTERNS: dict[DiataxisType, tuple[Pattern[str], ...]] = {
    DiataxisType.TUTORIAL: (
        re.compile(r"\blearn\b", re.IGNORECASE),
        re.compile(r"\bstep[- ]by[- ]step\b", re.IGNORECASE),
        re.compile(r"\bwalkthrough\b", re.IGNORECASE),
        re.compile(r"\bfollow along\b", re.IGNORECASE),
        re.compile(r"\blet's\b", re.IGNORECASE),
        re.compile(r"\byou will\b", re.IGNORECASE),
    ),
    DiataxisType.HOWTO: (
        re.compile(r"\bhow to\b", re.IGNORECASE),
        re.compile(r"\bguide\b", re.IGNORECASE),
        re.compile(r"\bsolve\b", re.IGNORECASE),
        re.compile(r"\bachieve\b", re.IGNORECASE),
        re.compile(r"\baccomplish\b", re.IGNORECASE),
        re.compile(r"\btask\b", re.IGNORECASE),
        re.compile(r"\bgoal\b", re.IGNORECASE),
    ),
    DiataxisType.REFERENCE: (
        re.compile(r"\bapi\b", re.IGNORECASE),
        re.compile(r"\bspecification\b", re.IGNORECASE),
        re.compile(r"\bschema\b", re.IGNORECASE),
        re.compile(r"\bformat\b", re.IGNORECASE),
        re.compile(r"\boptions?\b", re.IGNORECASE),
        re.compile(r"\bparameters?\b", re.IGNORECASE),
        re.compile(r"\bsyntax\b", re.IGNORECASE),
    ),
    DiataxisType.EXPLANATION: (
        re.compile(r"\bwhy\b", re.IGNORECASE),
        re.compile(r"\barchitecture\b", re.IGNORECASE),
        re.compile(r"\bdesign\b", re.IGNORECASE),
        re.compile(r"\bconcept\b", re.IGNORECASE),
        re.compile(r"\bunderstand\b", re.IGNORECASE),
        re.compile(r"\btheory\b", re.IGNORECASE),
        re.compile(r"\bbackground\b", re.IGNORECASE),
    ),
}

_PERSONA_PATTERNS: dict[PersonaType, tuple[Pattern[str], ...]] = {
    PersonaType.NOVICE: (
        re.compile(r"\bbeginner\b", re.IGNORECASE),
        re.compile(r"\bintroduction\b", re.IGNORECASE),
        re.compile(r"\bbasic\b", re.IGNORECASE),
        re.compile(r"\bfirst\b", re.IGNORECASE),
        re.compile(r"\bsimple\b", re.IGNORECASE),
        re.compile(r"\beasy\b", re.IGNORECASE),
        re.compile(r"\bstarting\b", re.IGNORECASE),
    ),
    PersonaType.EXPERT: (
        re.compile(r"\badvanced\b", re.IGNORECASE),
        re.compile(r"\bexpert\b", re.IGNORECASE),
        re.compile(r"\bprofessional\b", re.IGNORECASE),
        re.compile(r"\bdeep dive\b", re.IGNORECASE),
        re.compile(r"\barchitect\b", re.IGNORECASE),
        re.compile(r"\boptimiz\b", re.IGNORECASE),
        re.compile(r"\bperformance\b", re.IGNORECASE),
    ),
}

_DOMAIN_PATTERNS: dict[str, tuple[Pattern[str], ...]] = {
    "cli": (
        re.compile(r"\bcommand[- ]line\b", re.IGNORECASE),
        re.compile(r"\bcli\b", re.IGNORECASE),
        re.compile(r"\bterminal\b", re.IGNORECASE),
        re.compile(r"\bshell\b", re.IGNORECASE),
    ),
    "api": (
        re.compile(r"\bapi\b", re.IGNORECASE),
        re.compile(r"\bendpoint\b", re.IGNORECASE),
        re.compile(r"\brequest\b", re.IGNORECASE),
        re.compile(r"\bresponse\b", re.IGNORECASE),
    ),
    "config": (
        re.compile(r"\bconfig\b", re.IGNORECASE),
        re.compile(r"\bsettings?\b", re.IGNORECASE),
        re.compile(r"\byaml\b", re.IGNORECASE),
        re.compile(r"\bjson\b", re.IGNORECASE),
        re.compile(r"\btoml\b", re.IGNORECASE),
    ),
    "security": (
        re.compile(r"\bsecurity\b", re.IGNORECASE),
        re.compile(r"\bauth\b", re.IGNORECASE),
        re.compile(r"\btoken\b", re.IGNORECASE),
        re.compile(r"\bpermission\b", re.IGNORECASE),
    ),
    "testing": (
        re.compile(r"\btest\b", re.IGNORECASE),
        re.compile(r"\bpytest\b", re.IGNORECASE),
        re.compile(r"\bassert\b", re.IGNORECASE),
        re.compile(r"\bmock\b", re.IGNORECASE),
    ),
}

_HIGH_CERTAINTY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bmust\b", re.IGNORECASE),
    re.compile(r"\balways\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bdefinitely\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\b", re.IGNORECASE),
    re.compile(r"\brequired\b", re.IGNORECASE),
)

_LOW_CERTAINTY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bmaybe\b", re.IGNORECASE),
    re.compile(r"\bmight\b", re.IGNORECASE),
    re.compile(r"\bpossibly\b", re.IGNORECASE),
    re.compile(r"\bprobably\b", re.IGNORECASE),
    re.compile(r"\btypically\b", re.IGNORECASE),
    re.compile(r"\busually\b", re.IGNORECASE),
    re.compile(r"\bgenerally\b", re.IGNORECASE),
)



# =============================================================================
# Module-level extraction functions (formerly FacetExtractor methods)
# =============================================================================


def extract_facets_from_text(
    text: str,
    section: DocumentSection | None = None,
    source_type: str = "docs",
) -> ContentFacets:
    """Extract facets from text content.

    Args:
        text: The text to analyze.
        section: Optional document section for additional context.
        source_type: Source of the content ("docs", "code", "conversation", etc.).

    Returns:
        ContentFacets with detected facet values.
    """
    text_lower = text.lower()

    # Detect Diataxis type
    diataxis_type = _detect_diataxis(text_lower, section)

    # Detect persona
    persona = _detect_persona(text_lower)

    # Detect domains
    domains = _detect_domains(text_lower)

    # Infer confidence from indicators
    confidence = _infer_confidence(text_lower)

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
    text: str,
    section: DocumentSection | None,
) -> DiataxisType | None:
    """Detect Diataxis type from text and section."""
    from sunwell.memory.simulacrum.topology.structural import SectionType

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
    for dtype, patterns in _DIATAXIS_PATTERNS.items():
        scores[dtype] = sum(1 for p in patterns if p.search(text))

    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        if best[1] > 0:
            return best[0]

    return None


def _detect_persona(text: str) -> PersonaType | None:
    """Detect target persona from text."""
    scores: dict[PersonaType, int] = {}
    for persona, patterns in _PERSONA_PATTERNS.items():
        scores[persona] = sum(1 for p in patterns if p.search(text))

    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        if best[1] > 0:
            return best[0]

    # Default to pragmatist if no clear signal
    return PersonaType.PRAGMATIST


def _detect_domains(text: str) -> list[str]:
    """Detect domain tags from text."""
    domains = []
    for domain, patterns in _DOMAIN_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            domains.append(domain)
    return domains


def _infer_confidence(text: str) -> ConfidenceLevel:
    """Infer confidence level from uncertainty markers."""
    high_count = sum(1 for p in _HIGH_CERTAINTY_PATTERNS if p.search(text))
    low_count = sum(1 for p in _LOW_CERTAINTY_PATTERNS if p.search(text))

    if high_count > low_count and high_count > 2:
        return ConfidenceLevel.HIGH
    elif low_count > high_count and low_count > 2:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.MODERATE


