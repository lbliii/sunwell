"""Briefing-Based Skill and Lens Routing (RFC-071).

Analyzes the briefing's `next_action` and other signals to predict what
skills/heuristics will be needed and suggest an appropriate lens.

This enables the prefetch system to load the right context before the
main agent starts.
"""


import re

from sunwell.memory.briefing import Briefing

# Skill patterns: regex → list of skills to activate
SKILL_PATTERNS: dict[str, list[str]] = {
    # Testing patterns
    r"test|spec|coverage|assert|pytest|unittest": ["testing", "pytest", "coverage"],
    # Debugging patterns
    r"fix|bug|error|debug|broken|issue|crash": ["debugging", "error_analysis", "logging"],
    # Refactoring patterns
    r"refactor|clean|extract|rename|restructure|simplify": [
        "refactoring",
        "code_quality",
    ],
    # API patterns
    r"endpoint|route|api|rest|graphql|http|request": [
        "api_design",
        "http",
        "serialization",
    ],
    # Security patterns
    r"auth|security|permission|token|jwt|oauth|encrypt": [
        "security",
        "auth",
        "crypto",
    ],
    # Performance patterns
    r"optimi|perf|fast|slow|cache|async|parallel": [
        "performance",
        "profiling",
        "caching",
    ],
    # Database patterns
    r"database|sql|query|model|migrate|schema": ["database", "orm", "sql"],
    # Frontend patterns
    r"ui|frontend|component|style|css|html|react|svelte": [
        "frontend",
        "ui_design",
        "components",
    ],
    # DevOps patterns
    r"deploy|docker|ci|cd|pipeline|kubernetes|k8s": ["devops", "deployment", "ci_cd"],
    # Documentation patterns
    r"doc|readme|comment|docstring|api.?doc": ["documentation", "writing"],
}

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
    for pattern, skills in SKILL_PATTERNS.items():
        if re.search(pattern, text):
            needed_skills.extend(skills)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_skills: list[str] = []
    for skill in needed_skills:
        if skill not in seen:
            seen.add(skill)
            unique_skills.append(skill)

    return unique_skills


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
