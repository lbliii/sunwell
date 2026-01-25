"""Intent Extraction (RFC-072 prep for RFC-075).

Extracts intent signals from goals to inform surface composition.
RFC-075 will extend this with LLM-based intent analysis.
"""

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

# Pre-compiled regex for tokenization (avoid per-call compilation)
_RE_WORD_TOKEN = re.compile(r"\b[a-z]+\b")

# Domain type
Domain = Literal["code", "planning", "writing", "data", "universal"]


@dataclass(frozen=True, slots=True)
class IntentSignals:
    """Extracted signals from a goal.

    These signals inform which primitives to surface and how to arrange them.
    """

    primary_domain: Domain
    """Most likely domain based on keywords."""

    domain_scores: MappingProxyType[Domain, float] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """Score for each domain (0.0-1.0). Immutable mapping."""

    triggered_primitives: tuple[str, ...] = ()
    """Primitive IDs triggered by keywords."""

    keywords: tuple[str, ...] = ()
    """Extracted keywords from goal."""

    suggested_arrangement: str = "standard"
    """Suggested layout arrangement."""

    confidence: float = 0.5
    """Confidence in the extraction (0.0-1.0)."""


# =============================================================================
# KEYWORD DICTIONARIES
# =============================================================================

# Domain keywords with weights
DOMAIN_KEYWORDS: dict[Domain, dict[str, float]] = {
    "code": {
        "code": 1.0,
        "implement": 1.0,
        "build": 0.9,
        "fix": 0.9,
        "bug": 0.9,
        "refactor": 0.9,
        "debug": 0.9,
        "api": 0.8,
        "function": 0.8,
        "class": 0.8,
        "test": 0.7,
        "deploy": 0.7,
        "run": 0.6,
        "compile": 0.8,
        "lint": 0.7,
        "type": 0.6,
        "error": 0.7,
        "exception": 0.7,
        "module": 0.7,
        "import": 0.6,
        "dependency": 0.7,
        "package": 0.7,
    },
    "planning": {
        "plan": 1.0,
        "roadmap": 1.0,
        "sprint": 0.9,
        "task": 0.8,
        "milestone": 0.9,
        "schedule": 0.8,
        "kanban": 1.0,
        "board": 0.7,
        "goal": 0.8,
        "objective": 0.8,
        "deadline": 0.8,
        "timeline": 0.9,
        "backlog": 0.9,
        "priority": 0.7,
        "estimate": 0.7,
        "velocity": 0.8,
        "progress": 0.6,
        "track": 0.6,
        "organize": 0.6,
    },
    "writing": {
        "write": 0.9,
        "document": 0.9,
        "article": 1.0,
        "blog": 1.0,
        "readme": 0.8,
        "tutorial": 0.8,
        "guide": 0.7,
        "novel": 1.0,
        "story": 0.9,
        "chapter": 0.9,
        "draft": 0.8,
        "edit": 0.6,
        "prose": 1.0,
        "content": 0.6,
        "paragraph": 0.7,
        "outline": 0.8,
        "manuscript": 1.0,
        "essay": 0.9,
    },
    "data": {
        "data": 0.9,
        "analyze": 1.0,
        "chart": 1.0,
        "table": 0.8,
        "query": 0.9,
        "sql": 1.0,
        "csv": 0.9,
        "excel": 0.8,
        "spreadsheet": 0.9,
        "visualize": 0.9,
        "graph": 0.8,
        "metric": 0.7,
        "dashboard": 0.9,
        "report": 0.7,
        "aggregate": 0.8,
        "filter": 0.6,
        "statistics": 0.9,
    },
}

# Primitive triggers - keywords that specifically trigger certain primitives
PRIMITIVE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "Terminal": ("terminal", "shell", "command", "run", "execute", "bash", "cli"),
    "TestRunner": ("test", "coverage", "spec", "verify", "assert", "unittest"),
    "DiffView": ("diff", "compare", "change", "review", "merge", "conflict"),
    "Preview": ("preview", "web", "browser", "render", "live"),
    "Dependencies": ("dependency", "package", "import", "install", "npm", "pip", "cargo"),
    "Timeline": ("timeline", "roadmap", "gantt", "schedule", "deadline"),
    "Kanban": ("kanban", "board", "column", "task", "sprint"),
    "GoalTree": ("goal", "objective", "hierarchy", "breakdown"),
    "TaskList": ("today", "next", "priority", "todo", "checklist"),
    "Calendar": ("calendar", "date", "week", "month", "appointment"),
    "Metrics": ("metric", "progress", "velocity", "kpi", "stat"),
    "Outline": ("outline", "structure", "toc", "heading", "section"),
    "References": ("reference", "citation", "link", "source", "bibliography"),
    "WordCount": ("word", "count", "length", "stat"),
    "Chart": ("chart", "graph", "plot", "visualize", "bar", "line", "pie"),
    "QueryBuilder": ("query", "sql", "filter", "search", "find"),
    "MemoryPane": ("memory", "decision", "learned", "pattern", "before", "last time", "previous"),
    "DAGView": ("dag", "pipeline", "workflow", "execution", "plan"),
}

# Arrangement triggers
ARRANGEMENT_TRIGGERS: dict[str, tuple[str, ...]] = {
    "focused": ("focus", "distraction-free", "zen", "minimal", "concentrate"),
    "split": ("compare", "side-by-side", "dual", "both"),
    "dashboard": ("dashboard", "overview", "multi", "all"),
}


def extract_intent(goal: str) -> IntentSignals:
    """Extract intent signals from a goal string.

    This is the heuristic extraction that will be enhanced by RFC-075's
    LLM-based intent analysis.

    Args:
        goal: User's goal string

    Returns:
        Extracted intent signals
    """
    goal_lower = goal.lower()
    words = _tokenize(goal_lower)

    # Score each domain
    domain_scores = _score_domains(words)

    # Find primary domain
    primary_domain: Domain = max(domain_scores, key=lambda d: domain_scores[d])

    # Find triggered primitives
    triggered = _find_triggered_primitives(goal_lower)

    # Determine arrangement
    arrangement = _determine_arrangement(goal_lower)

    # Calculate confidence based on signal strength
    max_score = max(domain_scores.values())
    confidence = min(0.9, max_score * 1.2)  # Cap at 0.9 for heuristic extraction

    return IntentSignals(
        primary_domain=primary_domain,
        domain_scores=domain_scores,
        triggered_primitives=triggered,
        keywords=tuple(words),
        suggested_arrangement=arrangement,
        confidence=confidence,
    )


def _tokenize(text: str) -> list[str]:
    """Tokenize text into words."""
    # Split on non-alphanumeric, filter short words (uses pre-compiled regex)
    words = _RE_WORD_TOKEN.findall(text)
    return [w for w in words if len(w) > 2]


def _score_domains(words: list[str]) -> MappingProxyType[Domain, float]:
    """Score each domain based on keyword matches."""
    scores: dict[Domain, float] = {
        "code": 0.0,
        "planning": 0.0,
        "writing": 0.0,
        "data": 0.0,
        "universal": 0.1,  # Small base score
    }

    for word in words:
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if word in keywords:
                scores[domain] += keywords[word]

    # Normalize scores
    total = sum(scores.values())
    if total > 0:
        for domain in scores:
            scores[domain] /= total

    return MappingProxyType(scores)


def _find_triggered_primitives(goal_lower: str) -> tuple[str, ...]:
    """Find primitives triggered by keywords in goal."""
    triggered = []

    for primitive_id, triggers in PRIMITIVE_TRIGGERS.items():
        for trigger in triggers:
            if trigger in goal_lower:
                triggered.append(primitive_id)
                break  # Only add each primitive once

    return tuple(triggered)


def _determine_arrangement(goal_lower: str) -> str:
    """Determine suggested arrangement from goal."""
    for arrangement, triggers in ARRANGEMENT_TRIGGERS.items():
        for trigger in triggers:
            if trigger in goal_lower:
                return arrangement

    return "standard"


def match_triggers(trigger_pattern: str | None, goal: str) -> bool:
    """Check if a trigger pattern matches a goal.

    Trigger patterns are pipe-separated keywords (e.g., "test|coverage|verify").

    Args:
        trigger_pattern: Pipe-separated trigger keywords, or None
        goal: Goal to check against

    Returns:
        True if any trigger keyword matches
    """
    if not trigger_pattern:
        return False

    goal_lower = goal.lower()
    triggers = trigger_pattern.split("|")

    return any(trigger.strip() in goal_lower for trigger in triggers)
