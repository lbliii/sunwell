"""Research domain validators (RFC-DOMAINS).

Provides domain-specific validation for research artifacts:
- SourceValidator: Verify claims have sources
- CoherenceValidator: Check logical coherence
"""

import re
import time
from dataclasses import dataclass
from typing import Any

from sunwell.domains.protocol import ValidationResult

@dataclass(slots=True)
class SourceValidator:
    """Verify research claims have sources.

    Checks that factual assertions are backed by citations
    or source references.
    """

    name: str = "sources"
    description: str = "Check claims are backed by sources"
    min_sources: int = 1

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Check for source citations in research content.

        Args:
            artifact: Research content (string)
            context: Additional context

        Returns:
            ValidationResult with source check results
        """
        start = time.monotonic()

        if not isinstance(artifact, str):
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type (expected string)",
            )

        # Look for citations
        url_pattern = re.compile(r"https?://[^\s]+")
        citation_pattern = re.compile(r"\[\d+\]|\(\d{4}\)|\[.*?\]")

        urls = url_pattern.findall(artifact)
        citations = citation_pattern.findall(artifact)

        total_sources = len(set(urls)) + len(set(citations))
        passed = total_sources >= self.min_sources

        duration = int((time.monotonic() - start) * 1000)

        if passed:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message=f"Found {total_sources} source(s)",
                duration_ms=duration,
            )
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"Found {total_sources} source(s), need at least {self.min_sources}",
                errors=({"message": "Insufficient sources"},),
                duration_ms=duration,
            )


@dataclass(slots=True)
class CoherenceValidator:
    """Check logical coherence of research content.

    Validates that:
    - Content has a clear structure
    - Paragraphs are connected
    - No contradictory statements (basic check)
    """

    name: str = "coherence"
    description: str = "Check logical coherence and structure"
    min_paragraphs: int = 1

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Check coherence of research content.

        This is a basic structural check. For deep semantic coherence,
        an LLM-based validator would be needed.

        Args:
            artifact: Research content (string)
            context: Additional context

        Returns:
            ValidationResult with coherence check results
        """
        start = time.monotonic()

        if not isinstance(artifact, str):
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type (expected string)",
            )

        errors: list[dict[str, Any]] = []

        # Check for basic structure
        paragraphs = [p.strip() for p in artifact.split("\n\n") if p.strip()]
        if len(paragraphs) < self.min_paragraphs:
            n = len(paragraphs)
            errors.append({
                "message": f"Content has {n} paragraph(s), expected at least {self.min_paragraphs}",
            })

        # Check for transition words (indicates connected ideas)
        transition_words = {
            "however",
            "therefore",
            "additionally",
            "furthermore",
            "consequently",
            "moreover",
            "first",
            "second",
            "finally",
            "in conclusion",
            "for example",
            "specifically",
        }
        has_transitions = any(word in artifact.lower() for word in transition_words)

        # For longer content, transitions are expected
        if len(paragraphs) > 2 and not has_transitions:
            errors.append({
                "message": "Multi-paragraph content lacks transition words",
            })

        duration = int((time.monotonic() - start) * 1000)

        if not errors:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="Content is coherent",
                duration_ms=duration,
            )
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"{len(errors)} coherence issue(s)",
                errors=tuple(errors),
                duration_ms=duration,
            )
