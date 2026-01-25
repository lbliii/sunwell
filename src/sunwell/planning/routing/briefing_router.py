"""Briefing-Based Skill and Lens Routing (RFC-071).

Analyzes the briefing's `next_action` and other signals to predict what
skills/heuristics will be needed and suggest an appropriate lens.

This enables the prefetch system to load the right context before the
main agent starts.
"""

import re

from sunwell.memory.briefing import Briefing

# Pre-compiled skill patterns: (pattern, skills) tuples for O(1) matching per pattern
_SKILL_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    # Testing patterns
    (re.compile(r"test|spec|coverage|assert|pytest|unittest"), ("testing", "pytest", "coverage")),
    # Debugging patterns
    (re.compile(r"fix|bug|error|debug|broken|issue|crash"), ("debugging", "error_analysis", "logging")),
    # Refactoring patterns
    (re.compile(r"refactor|clean|extract|rename|restructure|simplify"), ("refactoring", "code_quality")),
    # API patterns
    (re.compile(r"endpoint|route|api|rest|graphql|http|request"), ("api_design", "http", "serialization")),
    # Security patterns
    (re.compile(r"auth|security|permission|token|jwt|oauth|encrypt"), ("security", "auth", "crypto")),
    # Performance patterns
    (re.compile(r"optimi|perf|fast|slow|cache|async|parallel"), ("performance", "profiling", "caching")),
    # Database patterns
    (re.compile(r"database|sql|query|model|migrate|schema"), ("database", "orm", "sql")),
    # Frontend patterns
    (re.compile(r"ui|frontend|component|style|css|html|react|svelte"), ("frontend", "ui_design", "components")),
    # DevOps patterns
    (re.compile(r"deploy|docker|ci|cd|pipeline|kubernetes|k8s"), ("devops", "deployment", "ci_cd")),
    # Documentation patterns
    (re.compile(r"doc|readme|comment|docstring|api.?doc"), ("documentation", "writing")),
)

# Lens mapping: primary skill → lens name
LENS_MAPPING: dict[str, str] = {
    "testing": "qa-engineer",
    "debugging": "debugger",
    "refactoring": "refactorer",
    "api_design": "api-architect",
    "security": "security-reviewer",
    "performance": "performance-engineer",
    "database": "data-engineer",
    "frontend": "frontend-engineer",
    "devops": "devops-engineer",
    "documentation": "technical-writer",
}


def predict_skills_from_briefing(briefing: Briefing) -> list[str]:
    """Predict needed skills from briefing signals.

    Analyzes the briefing's next_action, progress, and hazards to
    determine what skills/heuristics will likely be needed.

    Args:
        briefing: The current briefing

    Returns:
        List of skill names that should be activated
    """
    # Combine relevant text fields
    text_parts = [
        briefing.next_action or "",
        briefing.progress,
        " ".join(briefing.hazards),
        briefing.mission,
    ]
    text = " ".join(text_parts).lower()

    needed_skills: list[str] = []
    for pattern, skills in _SKILL_PATTERNS:
        if pattern.search(text):
            needed_skills.extend(skills)

    # Deduplicate while preserving order (dict.fromkeys preserves insertion order)
    return list(dict.fromkeys(needed_skills))


def suggest_lens_from_briefing(briefing: Briefing) -> str | None:
    """Suggest best lens based on predicted work type.

    Uses the predicted skills to determine which lens would be
    most appropriate for the upcoming work.

    Args:
        briefing: The current briefing

    Returns:
        Lens name if a match is found, None for default lens
    """
    skills = predict_skills_from_briefing(briefing)

    # Return first matching lens
    for skill in skills:
        if skill in LENS_MAPPING:
            return LENS_MAPPING[skill]

    return None  # Use default lens
