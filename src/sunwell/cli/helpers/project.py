"""Project name extraction helpers."""

import re

# Pre-compiled patterns for project name extraction (avoid recompiling per call)
_RE_PROJECT_NAME_PATTERNS = (
    re.compile(r"(?:build|create|make|write)\s+(?:a\s+)?(.+?)\s+(?:app|api|tool|site|website|service)"),
    re.compile(r"(?:build|create|make|write)\s+(?:a\s+)?(.+?)\s+(?:with|using)"),
    re.compile(r"(?:build|create|make)\s+(?:a\s+)?(.+?)$"),
)


def extract_project_name(goal: str) -> str | None:
    """Extract a project name hint from a goal.

    Simple heuristic extraction - looks for common patterns like
    "build a X app" or "create X".

    Args:
        goal: Natural language goal

    Returns:
        Extracted project name or None if unclear
    """
    goal_lower = goal.lower()

    # Pattern: "build/create/make a X app/api/tool/site"
    for pattern in _RE_PROJECT_NAME_PATTERNS:
        match = pattern.search(goal_lower)
        if match:
            name = match.group(1).strip()
            # Filter out very short or generic results
            if len(name) > 2 and name not in ("a", "an", "the", "new", "simple"):
                return name

    return None
