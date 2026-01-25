"""Confidence rubric for deterministic scoring (RFC-022).

Replaces "LLM vibes" with explicit scoring rules.
"""

import re
from dataclasses import dataclass
from typing import Any

from sunwell.planning.routing.types import ExecutionTier

# Pre-compiled regex for file extension detection
_RE_FILE_EXTENSION = re.compile(r'\b\w+\.(py|js|ts|md|yaml|json|go|rs|java|c|cpp|h)\b')


@dataclass(frozen=True, slots=True)
class ConfidenceRubric:
    """Deterministic confidence scoring rubric.

    Replaces "LLM vibes" with explicit scoring rules.
    Each signal adds or subtracts from a base score of 50.
    """

    base_score: int = 50

    # Positive signals (add points)
    explicit_shortcut: int = 20      # ::command patterns
    clear_action_verb: int = 15      # review, test, document
    single_file_target: int = 15     # Explicit file mentioned
    file_state_match: int = 10       # File exists/doesn't as expected
    exemplar_match_high: int = 10    # >0.85 similarity to exemplar
    exemplar_match_mod: int = 5      # >0.7 similarity to exemplar

    # Negative signals (subtract points)
    no_file_context: int = -20       # No file mentioned or focused
    ambiguous_verb: int = -15        # fix, help, improve
    multi_file_scope: int = -15      # Multiple files mentioned
    conflicting_signals: int = -10   # Contradictory hints
    no_exemplar_match: int = -10     # <0.5 similarity to any exemplar

    # Action verb sets
    CLEAR_VERBS: frozenset[str] = frozenset({
        "review", "audit", "check", "validate",
        "test", "write", "create", "add",
        "document", "explain", "describe",
        "refactor", "extract", "rename",
        "debug", "trace", "profile",
    })

    AMBIGUOUS_VERBS: frozenset[str] = frozenset({
        "fix", "help", "improve", "update", "change", "modify",
        "look", "handle", "deal", "work",
    })

    def calculate(
        self,
        task: str,
        context: dict[str, Any] | None,
        exemplar_similarity: float | None,
    ) -> tuple[int, str]:
        """Calculate confidence score with explanation.

        Args:
            task: The user's request
            context: Optional context (file info, etc.)
            exemplar_similarity: Similarity to best matching exemplar (0-1)

        Returns:
            Tuple of (score 0-100, explanation string)
        """
        score = self.base_score
        reasons: list[str] = []

        task_lower = task.lower()
        words = task_lower.split()

        # Check for explicit shortcut
        if task.strip().startswith("::"):
            score += self.explicit_shortcut
            reasons.append(f"+{self.explicit_shortcut} explicit shortcut")

        # Check for clear action verb
        if any(verb in words for verb in self.CLEAR_VERBS):
            score += self.clear_action_verb
            reasons.append(f"+{self.clear_action_verb} clear action verb")

        # Check for ambiguous verb
        if any(verb in words for verb in self.AMBIGUOUS_VERBS):
            score += self.ambiguous_verb  # Negative
            reasons.append(f"{self.ambiguous_verb} ambiguous verb")

        # Check file context
        has_file = context and (context.get("file") or context.get("focused_file"))
        file_in_task = bool(_RE_FILE_EXTENSION.search(task))

        if has_file or file_in_task:
            score += self.single_file_target
            reasons.append(f"+{self.single_file_target} file target")
        elif not has_file and not file_in_task:
            score += self.no_file_context  # Negative
            reasons.append(f"{self.no_file_context} no file context")

        # Check multi-file scope
        file_matches = _RE_FILE_EXTENSION.findall(task)
        if len(file_matches) > 1:
            score += self.multi_file_scope  # Negative
            reasons.append(f"{self.multi_file_scope} multi-file scope")

        # Check exemplar similarity
        if exemplar_similarity is not None:
            if exemplar_similarity > 0.85:
                score += self.exemplar_match_high
                reasons.append(
                    f"+{self.exemplar_match_high} high exemplar match ({exemplar_similarity:.2f})"
                )
            elif exemplar_similarity > 0.7:
                score += self.exemplar_match_mod
                reasons.append(
                    f"+{self.exemplar_match_mod} moderate match ({exemplar_similarity:.2f})"
                )
            elif exemplar_similarity < 0.5:
                score += self.no_exemplar_match  # Negative
                reasons.append(
                    f"{self.no_exemplar_match} low exemplar match ({exemplar_similarity:.2f})"
                )

        # Clamp to 0-100
        score = max(0, min(100, score))

        if reasons:
            explanation = f"Base {self.base_score}: " + ", ".join(reasons)
        else:
            explanation = f"Base {self.base_score}"
        return score, explanation

    def to_confidence_level(self, score: int) -> str:
        """Convert score to confidence level string."""
        if score >= 80:
            return "HIGH"
        elif score >= 60:
            return "MEDIUM"
        else:
            return "LOW"

    def score_to_tier(self, score: int, has_shortcut: bool) -> ExecutionTier:
        """Determine execution tier from confidence score."""
        if has_shortcut or score >= 85:
            return ExecutionTier.FAST
        elif score >= 60:
            return ExecutionTier.LIGHT
        else:
            return ExecutionTier.FULL


# Default rubric instance
DEFAULT_RUBRIC = ConfidenceRubric()
