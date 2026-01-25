"""Persona definitions and temperature strategies for Harmonic conditions."""

# Original personas (similar thinking, similar temperatures)
HARDCODED_PERSONAS: dict[str, str] = {
    "security": (
        "You are a security expert. Focus on attack vectors, "
        "defensive coding, and input validation."
    ),
    "quality": (
        "You are a code quality expert. Focus on clean, "
        "maintainable, idiomatic code."
    ),
    "testing": (
        "You are a QA engineer. Focus on testability, "
        "edge cases, and failure modes."
    ),
}

# Divergent personas (conceptually different perspectives)
DIVERGENT_PERSONAS: dict[str, tuple[str, float]] = {
    "adversary": (
        "You MUST find ways to break this. Assume the worst case. "
        "Look for security holes, edge cases that crash, race conditions. "
        "Be paranoid and adversarial.",
        0.4,  # Low temp: methodical, focused attack
    ),
    "advocate": (
        "You MUST defend this solution. Find its strengths. "
        "Explain why this approach is good. Be optimistic and supportive. "
        "Show how it solves the problem elegantly.",
        0.7,  # Medium temp: balanced defense
    ),
    "naive": (
        "You know NOTHING about this domain. Ask obvious questions. "
        "What would a complete beginner wonder? What's confusing? "
        "Point out things that seem weird or unexplained.",
        1.0,  # High temp: wild, unexpected questions
    ),
}


class TemperatureStrategy:
    """Temperature sampling strategies for Harmonic Synthesis."""

    UNIFORM_LOW = {"security": 0.5, "quality": 0.5, "testing": 0.5}
    UNIFORM_MED = {"security": 0.7, "quality": 0.7, "testing": 0.7}
    UNIFORM_HIGH = {"security": 0.9, "quality": 0.9, "testing": 0.9}
    SPREAD = {"security": 0.3, "quality": 0.7, "testing": 1.0}
    DIVERGENT = {k: v[1] for k, v in DIVERGENT_PERSONAS.items()}
