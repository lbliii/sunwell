"""Squash Extraction — Multi-perspective extraction with agreement synthesis.

The problem with naive multi-perspective extraction:
- Each perspective might hallucinate independently
- No grounding mechanism
- Large outputs

The solution: Extract → Compare → Keep Agreement → Synthesize

Like interference patterns:
- Constructive interference (perspectives agree) → High confidence fact
- Destructive interference (perspectives disagree) → Flag for review

Like swarm traces:
- Strong traces (multiple extractors found it) → Survives
- Weak traces (only one extractor found it) → Evaporates

Example:
    >>> result = await squash_extract(
    ...     document=rfc_content,
    ...     questions=["What is the tech stack?", "What are the requirements?"],
    ...     model=model,
    ... )
    >>> print(result.confident_facts)  # Only things all extractors agreed on
    >>> print(result.uncertain_items)   # Where extractors disagreed
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    """A single extracted fact with confidence."""

    content: str
    """The extracted content."""

    source_question: str
    """Which question extracted this."""

    extractor_count: int
    """How many extractors found this or similar."""

    confidence: float
    """0.0-1.0 based on agreement."""

    quotes: tuple[str, ...]
    """Direct quotes from document supporting this."""


@dataclass(frozen=True, slots=True)
class SquashResult:
    """Result from squash extraction."""

    document_preview: str
    """First ~200 chars of document."""

    questions: tuple[str, ...]
    """Questions asked."""

    # Results by confidence
    confident_facts: tuple[ExtractedFact, ...]
    """Facts with high agreement (confidence >= 0.7)."""

    uncertain_facts: tuple[ExtractedFact, ...]
    """Facts with low agreement (confidence < 0.7)."""

    # Synthesis
    synthesized_goal: str
    """Final compact goal synthesized from confident facts."""

    # Stats
    total_extractions: int
    """Total extraction calls made."""

    agreement_rate: float
    """Overall agreement rate across extractions."""


# =============================================================================
# Extraction Prompts
# =============================================================================

# Force extraction over inference by requiring quotes
EXTRACT_PROMPT = """Extract ONLY factual information from this document. Do NOT infer or assume.

DOCUMENT:
{document}

QUESTION: {question}

RULES:
1. Quote EXACT text from the document
2. If not explicitly stated, say "NOT SPECIFIED"
3. Do NOT guess or assume
4. Be concise (max 100 words)

Format your answer as:
FACT: [the factual answer]
QUOTE: "[exact quote from document]"
"""

# Section-specific questions that target relevant parts of RFCs
SECTION_QUESTIONS = {
    "tech_stack": {
        "sections": ["technical architecture", "stack", "technology", "implementation"],
        "question": "List the EXACT technologies, frameworks, and languages explicitly named.",
    },
    "goal": {
        "sections": ["summary", "overview", "motivation", "problem"],
        "question": "What is being built? Describe in one sentence.",
    },
    "phases": {
        "sections": ["implementation plan", "phase", "milestone", "timeline"],
        "question": "What implementation phases or milestones are defined?",
    },
    "ui": {
        "sections": ["user experience", "ux", "interface", "design"],
        "question": "What are the UI/UX requirements?",
    },
    "constraints": {
        "sections": ["non-goals", "constraints", "out of scope", "limitations"],
        "question": "What is explicitly excluded or out of scope?",
    },
}

SYNTHESIS_PROMPT = """Based on these verified facts extracted from a document, create a concise implementation goal.

VERIFIED FACTS:
{facts}

Create a goal statement that:
1. Captures the key requirements
2. Specifies the tech stack (if known)
3. Lists main deliverables
4. Is under 500 words

Goal:"""


# =============================================================================
# Core Extraction
# =============================================================================


async def _extract_once(
    document: str,
    question: str,
    model: ModelProtocol,
    doc_chunk_size: int = 6000,
) -> tuple[str, str | None]:
    """Run a single extraction, returning (fact, quote)."""
    from sunwell.models.protocol import GenerateOptions

    # Use first chunk of document (most important info usually at top)
    doc_chunk = document[:doc_chunk_size]

    prompt = EXTRACT_PROMPT.format(document=doc_chunk, question=question)

    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=300),  # Low temp for factual
    )

    response = result.text.strip()

    # Parse response
    fact = None
    quote = None

    fact_match = re.search(r"FACT:\s*(.+?)(?=QUOTE:|$)", response, re.DOTALL | re.IGNORECASE)
    if fact_match:
        fact = fact_match.group(1).strip()

    quote_match = re.search(r'QUOTE:\s*["\']?(.+?)["\']?\s*$', response, re.DOTALL | re.IGNORECASE)
    if quote_match:
        quote = quote_match.group(1).strip()

    return fact or response, quote


async def _extract_multiple(
    document: str,
    question: str,
    model: ModelProtocol,
    n_extractions: int = 3,
) -> list[tuple[str, str | None]]:
    """Run multiple extractions for the same question."""
    # Run extractions in parallel
    tasks = [_extract_once(document, question, model) for _ in range(n_extractions)]
    return await asyncio.gather(*tasks)


def _measure_agreement(extractions: list[tuple[str, str | None]]) -> tuple[str, float, list[str]]:
    """Find consensus and measure agreement among extractions.

    Returns: (consensus_fact, agreement_score, supporting_quotes)
    """
    facts = [e[0] for e in extractions if e[0] and "NOT SPECIFIED" not in e[0].upper()]
    quotes = [e[1] for e in extractions if e[1]]

    if not facts:
        return "NOT SPECIFIED", 0.0, []

    # Find most common fact (by semantic similarity)
    if len(facts) == 1:
        return facts[0], 1.0, quotes

    # Group similar facts
    groups: list[list[str]] = []
    for fact in facts:
        placed = False
        for group in groups:
            # Check similarity to group representative
            sim = SequenceMatcher(None, fact.lower(), group[0].lower()).ratio()
            if sim > 0.6:  # Similar enough
                group.append(fact)
                placed = True
                break
        if not placed:
            groups.append([fact])

    # Find largest group
    largest_group = max(groups, key=len)
    consensus = largest_group[0]  # Use first as representative
    agreement = len(largest_group) / len(facts)

    return consensus, agreement, quotes


async def squash_extract(
    document: str,
    questions: list[str],
    model: ModelProtocol,
    n_extractions: int = 3,
    confidence_threshold: float = 0.7,
) -> SquashResult:
    """Extract facts from document with agreement-based confidence.

    Args:
        document: The document to extract from
        questions: Questions to ask (e.g., ["What is the tech stack?", "What are the goals?"])
        model: Model to use for extraction
        n_extractions: How many times to extract each question (for agreement)
        confidence_threshold: Minimum agreement to count as confident

    Returns:
        SquashResult with confident facts, uncertain facts, and synthesized goal
    """
    from sunwell.models.protocol import GenerateOptions

    confident_facts: list[ExtractedFact] = []
    uncertain_facts: list[ExtractedFact] = []
    total_extractions = 0

    # Extract each question multiple times
    for question in questions:
        extractions = await _extract_multiple(document, question, model, n_extractions)
        total_extractions += len(extractions)

        consensus, agreement, quotes = _measure_agreement(extractions)

        fact = ExtractedFact(
            content=consensus,
            source_question=question,
            extractor_count=int(agreement * n_extractions),
            confidence=agreement,
            quotes=tuple(quotes[:2]),  # Keep top 2 quotes
        )

        if agreement >= confidence_threshold and "NOT SPECIFIED" not in consensus.upper():
            confident_facts.append(fact)
        else:
            uncertain_facts.append(fact)

    # Calculate overall agreement
    all_agreements = [f.confidence for f in confident_facts + uncertain_facts]
    overall_agreement = sum(all_agreements) / len(all_agreements) if all_agreements else 0.0

    # Synthesize goal from confident facts only
    if confident_facts:
        facts_str = "\n".join(
            f"- {f.source_question}: {f.content}" for f in confident_facts
        )
        synth_prompt = SYNTHESIS_PROMPT.format(facts=facts_str)
        synth_result = await model.generate(
            synth_prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=500),
        )
        synthesized = synth_result.text.strip()
    else:
        synthesized = "Insufficient confident facts to synthesize goal."

    return SquashResult(
        document_preview=document[:200] + "..." if len(document) > 200 else document,
        questions=tuple(questions),
        confident_facts=tuple(confident_facts),
        uncertain_facts=tuple(uncertain_facts),
        synthesized_goal=synthesized,
        total_extractions=total_extractions,
        agreement_rate=overall_agreement,
    )


# =============================================================================
# Convenience for Plan Command
# =============================================================================


def _find_section(document: str, section_keywords: list[str], max_chars: int = 3000) -> str | None:
    """Find a specific section in a document by keywords."""
    doc_lower = document.lower()
    
    for keyword in section_keywords:
        # Look for ## Section Header pattern
        pattern = rf"##\s*[^#\n]*{re.escape(keyword)}[^#\n]*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, doc_lower, re.DOTALL | re.IGNORECASE)
        if match:
            # Get the actual section from original document (preserve case)
            start = match.start()
            section = document[start:start + max_chars]
            return section
    
    return None


async def section_aware_extract(
    document: str,
    model: ModelProtocol,
    n_extractions: int = 2,
) -> SquashResult:
    """Extract from specific sections rather than whole document.
    
    This is more accurate because:
    1. Finds relevant sections by keywords
    2. Extracts from those sections specifically  
    3. Avoids whole-doc inference that leads to hallucination
    """
    from sunwell.models.protocol import GenerateOptions
    
    confident_facts: list[ExtractedFact] = []
    uncertain_facts: list[ExtractedFact] = []
    total_extractions = 0
    
    for key, config in SECTION_QUESTIONS.items():
        section = _find_section(document, config["sections"])
        
        if not section:
            # Section not found - mark as uncertain
            uncertain_facts.append(ExtractedFact(
                content="NOT FOUND",
                source_question=config["question"],
                extractor_count=0,
                confidence=0.0,
                quotes=(),
            ))
            continue
        
        # Extract from this specific section
        extractions = await _extract_multiple(
            section,  # Use section, not whole doc!
            config["question"],
            model,
            n_extractions,
        )
        total_extractions += len(extractions)
        
        consensus, agreement, quotes = _measure_agreement(extractions)
        
        fact = ExtractedFact(
            content=consensus,
            source_question=config["question"],
            extractor_count=int(agreement * n_extractions),
            confidence=agreement,
            quotes=tuple(quotes[:2]),
        )
        
        if agreement >= 0.5 and "NOT SPECIFIED" not in consensus.upper():
            confident_facts.append(fact)
        else:
            uncertain_facts.append(fact)
    
    # Calculate overall agreement
    all_agreements = [f.confidence for f in confident_facts + uncertain_facts if f.confidence > 0]
    overall_agreement = sum(all_agreements) / len(all_agreements) if all_agreements else 0.0
    
    # Synthesize from confident facts
    if confident_facts:
        facts_str = "\n".join(
            f"- {f.source_question}: {f.content}" for f in confident_facts
        )
        synth_prompt = SYNTHESIS_PROMPT.format(facts=facts_str)
        synth_result = await model.generate(
            synth_prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=500),
        )
        synthesized = synth_result.text.strip()
    else:
        synthesized = "Insufficient confident facts to synthesize goal."
    
    return SquashResult(
        document_preview=document[:200] + "..." if len(document) > 200 else document,
        questions=tuple(config["question"] for config in SECTION_QUESTIONS.values()),
        confident_facts=tuple(confident_facts),
        uncertain_facts=tuple(uncertain_facts),
        synthesized_goal=synthesized,
        total_extractions=total_extractions,
        agreement_rate=overall_agreement,
    )


async def extract_goal_with_squash(
    document: str,
    model: ModelProtocol,
    section_aware: bool = True,
) -> str:
    """Extract a planning goal from a document using squash extraction.

    This is the recommended way to extract goals from large documents.
    
    Args:
        document: The document to extract from
        model: Model to use
        section_aware: If True, find relevant sections first (recommended)
    """
    if section_aware:
        result = await section_aware_extract(document, model)
    else:
        # Fallback to whole-doc extraction
        planning_questions = [
            "What is being built? Describe the product/feature in one sentence.",
            "What is the specified technology stack? List frameworks, languages, tools.",
            "What are the UI/UX requirements? List key screens and interactions.",
            "What implementation phases or milestones are defined?",
            "What are the explicit constraints or non-goals?",
        ]

        result = await squash_extract(
            document=document,
            questions=planning_questions,
            model=model,
            n_extractions=3,
            confidence_threshold=0.6,
        )

    return result.synthesized_goal
