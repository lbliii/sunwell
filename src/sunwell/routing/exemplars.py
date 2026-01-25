"""Routing exemplars for pattern matching (RFC-022).

Gold-standard routing examples used for confidence calibration
and self-verification.
"""

from dataclasses import dataclass

from sunwell.routing.types import Intent


@dataclass(frozen=True, slots=True)
class RoutingExemplar:
    """Gold-standard routing example for pattern matching.

    Exemplars teach the router what good routing looks like.
    Used for confidence calibration and self-verification.
    """

    input: str                     # User request pattern
    context_hints: tuple[str, ...] # Expected context signals
    reasoning: str                 # Why this routing is correct
    intent: Intent                 # Correct intent
    lens: str                      # Correct lens
    focus: tuple[str, ...]         # Correct focus terms
    confidence: str                # HIGH | MEDIUM | LOW
    tags: tuple[str, ...]          # For retrieval matching


# Gold-standard exemplar bank
ROUTING_EXEMPLARS: tuple[RoutingExemplar, ...] = (
    # --- CODE REVIEW ---
    RoutingExemplar(
        input="review auth.py for security",
        context_hints=("file exists", "has auth code"),
        reasoning="Goal: security review | Scope: single file | Clear intent",
        intent=Intent.REVIEW,
        lens="code-reviewer",
        focus=("security", "authentication", "injection"),
        confidence="HIGH",
        tags=("security", "review", "auth"),
    ),
    RoutingExemplar(
        input="check this for bugs",
        context_hints=("recently edited",),
        reasoning="Goal: find bugs | Scope: single file | AMBIGUOUS - could mean logic/security",
        intent=Intent.REVIEW,
        lens="code-reviewer",
        focus=("logic", "edge_cases", "error_handling"),
        confidence="MEDIUM",
        tags=("bugs", "review", "check"),
    ),
    RoutingExemplar(
        input="::review @auth.py --security",
        context_hints=("explicit command",),
        reasoning="Explicit shortcut with target - deterministic routing",
        intent=Intent.REVIEW,
        lens="code-reviewer",
        focus=("security",),
        confidence="HIGH",
        tags=("command", "review", "security"),
    ),
    # --- CODE GENERATION ---
    RoutingExemplar(
        input="write a retry decorator",
        context_hints=(),
        reasoning="Goal: create code | Scope: single function | Clear intent",
        intent=Intent.CODE,
        lens="helper",
        focus=("retry", "decorator", "error_handling"),
        confidence="HIGH",
        tags=("write", "create", "decorator"),
    ),
    RoutingExemplar(
        input="add tests for the user service",
        context_hints=("no test file exists",),
        reasoning="Goal: create tests | Scope: single module | Clear intent",
        intent=Intent.CODE,
        lens="team-qa",
        focus=("unit_tests", "coverage", "edge_cases"),
        confidence="HIGH",
        tags=("test", "write", "create"),
    ),
    # --- EXPLANATION ---
    RoutingExemplar(
        input="explain how this works",
        context_hints=("code selected",),
        reasoning="Goal: understand code | Scope: selection | Clear intent",
        intent=Intent.EXPLAIN,
        lens="helper",
        focus=("explanation", "understanding"),
        confidence="HIGH",
        tags=("explain", "understand", "how"),
    ),
    RoutingExemplar(
        input="document this function",
        context_hints=("cursor on function",),
        reasoning="Goal: add docs | Scope: single function | Clear target",
        intent=Intent.CODE,
        lens="tech-writer",
        focus=("docstring", "parameters", "examples"),
        confidence="HIGH",
        tags=("document", "docstring", "function"),
    ),
    # --- DEBUG ---
    RoutingExemplar(
        input="why is this failing",
        context_hints=("error visible", "test failing"),
        reasoning="Goal: diagnose failure | Clear debug intent",
        intent=Intent.DEBUG,
        lens="debugger",
        focus=("error", "failure", "diagnosis"),
        confidence="HIGH",
        tags=("debug", "error", "failing"),
    ),
    RoutingExemplar(
        input="fix this",
        context_hints=(),
        reasoning="Goal: fix something | AMBIGUOUS - no target specified",
        intent=Intent.DEBUG,
        lens="helper",
        focus=("fix",),
        confidence="LOW",
        tags=("fix", "ambiguous"),
    ),
    # --- SEARCH ---
    RoutingExemplar(
        input="where is authentication implemented",
        context_hints=(),
        reasoning="Goal: find code | Exploration intent",
        intent=Intent.SEARCH,
        lens="helper",
        focus=("authentication", "location", "find"),
        confidence="HIGH",
        tags=("where", "find", "search"),
    ),
    # --- CHAT ---
    RoutingExemplar(
        input="hello",
        context_hints=(),
        reasoning="Greeting - casual conversation",
        intent=Intent.CHAT,
        lens="helper",
        focus=(),
        confidence="HIGH",
        tags=("greeting", "hello", "chat"),
    ),
)


def match_exemplar(
    task: str,
    exemplars: tuple[RoutingExemplar, ...] = ROUTING_EXEMPLARS,
) -> tuple[RoutingExemplar | None, float]:
    """Find best matching exemplar for a task.

    Uses simple keyword overlap scoring. Returns (best_exemplar, similarity).
    """
    task_lower = task.lower()
    task_words = set(task_lower.split())

    best_match: RoutingExemplar | None = None
    best_score = 0.0

    for exemplar in exemplars:
        # Score based on tag overlap
        exemplar_words = set(exemplar.tags)
        overlap = len(task_words & exemplar_words)
        total = len(task_words | exemplar_words)

        if total > 0:
            score = overlap / total

            # Boost if input pattern is similar
            if any(word in task_lower for word in exemplar.input.lower().split()[:3]):
                score += 0.2

            if score > best_score:
                best_score = score
                best_match = exemplar

    return best_match, min(1.0, best_score)


