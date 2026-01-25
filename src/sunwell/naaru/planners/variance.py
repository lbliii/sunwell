"""Variance strategies for Harmonic Planning (RFC-038)."""

from enum import Enum
from typing import Any


class VarianceStrategy(Enum):
    """Strategies for generating plan variance."""

    PROMPTING = "prompting"
    """Vary the discovery prompt emphasis (parallel-first, minimal, thorough)."""

    TEMPERATURE = "temperature"
    """Vary temperature (0.2, 0.4, 0.6) for different exploration."""

    CONSTRAINTS = "constraints"
    """Add different constraints (max depth, min parallelism)."""

    MIXED = "mixed"
    """Mix of prompting and temperature strategies."""


# Variance prompt templates - different prompts bias toward different plan shapes
#
# RFC-038/RFC-116: Each prompt should produce meaningfully different plan structures.
# Benchmark data (2026-01-24) showed:
# - parallel_first was NOT achieving high parallelism (0.27 vs target 0.5+)
# - balanced had low keyword coverage (0.67 vs 0.76)
# - minimal never won on V2 scoring
#
# Revised prompts address these issues with explicit structural targets.
VARIANCE_PROMPTS: dict[str, str] = {
    "parallel_first": """
OPTIMIZATION GOAL: MAXIMUM PARALLELISM (target: parallelism_factor > 0.5)

CRITICAL RULES:
1. At least 50% of artifacts MUST have ZERO dependencies (be leaves)
2. Maximum depth should be 2-3 levels, not deeper
3. When in doubt, make artifacts independent rather than dependent

Structural Pattern:
- Wave 1: Many independent leaf artifacts (models, interfaces, utilities)
- Wave 2: Integration artifacts that depend on Wave 1
- Wave 3 (max): Final assembly/root artifact

Do NOT create long sequential chains. If artifact B only exists to feed artifact C,
consider whether B and C can be independent instead.

Ask: "Does this artifact REALLY need that dependency, or could it be independent?"
""",
    "minimal": """
OPTIMIZATION GOAL: ESSENTIAL ARTIFACTS ONLY (while covering all goal keywords)

CRITICAL RULES:
1. Maximum 5-7 artifacts for any goal
2. Each artifact MUST directly address a keyword from the goal
3. Combine related functionality into single artifacts
4. No "nice to have" artifacts - only what's strictly required

Coverage Check:
Before finalizing, verify that every important word from the goal
appears in at least one artifact description.

Do NOT add tests, documentation, or validation as separate artifacts
unless explicitly requested in the goal.

Ask: "Would removing this artifact make the goal impossible to achieve?"
""",
    "thorough": """
OPTIMIZATION GOAL: COMPLETE PRODUCTION-READY COVERAGE

CRITICAL RULES:
1. Include error handling artifacts for each component
2. Include test artifacts for core functionality
3. Include validation/config artifacts where appropriate
4. Every keyword from the goal must appear in artifact descriptions

Coverage Targets:
- All happy paths covered
- All error paths covered
- Configuration/setup included
- Integration points explicit

This approach produces MORE artifacts but ensures nothing is missed.
Use when the goal is complex or production-readiness matters.

Ask: "What could go wrong? What's missing for production-ready?"
""",
    "modular": """
OPTIMIZATION GOAL: INDEPENDENT MODULES - MAXIMIZE PARALLEL WORK THROUGH ISOLATION

CRITICAL RULES:
1. Create artifacts that have NO dependencies on each other (maximize leaves)
2. Each artifact should be self-contained and testable in isolation
3. Prefer MANY SMALL independent artifacts over FEW LARGE coupled ones
4. Every goal keyword MUST appear in artifact descriptions

Structural Pattern (aim for depth ≤ 3):
- Wave 1: 3-5 independent module artifacts (data layer, logic, interface, config)
- Wave 2: Integration artifacts that combine modules
- Final: Root artifact that ties everything together

Key Insight: True modularity = high parallelism. 
If modules are truly independent, they can execute in parallel.
Target: parallelism_factor > 0.4

Ask: "Can this be split into independent pieces? Does this NEED that dependency?"
""",
    "risk_aware": """
OPTIMIZATION GOAL: FAIL-FAST - IDENTIFY RISKS EARLY

CRITICAL RULES:
1. Put highest-risk/uncertainty artifacts FIRST (as leaves)
2. Validate risky assumptions before building dependent artifacts
3. Critical path should surface failures early, not late
4. Every goal keyword MUST appear in artifact descriptions

Risk Categories (do these first):
- External dependencies (APIs, databases, third-party services)
- Novel/unfamiliar technology
- Performance-critical components
- Security-sensitive operations

Structural Pattern:
- Wave 1: Spike/validate risky components
- Wave 2: Core implementation (risks already validated)
- Wave 3: Integration and polish

This produces plans where failures happen early when they're cheap to fix.

Ask: "What could fail? What's uncertain? Should we validate that first?"
""",
    "default": """
Discover artifacts naturally based on the goal.
Focus on what must exist when the goal is complete.
Every important concept from the goal should appear in artifact descriptions.
""",
}


def get_variance_configs(
    strategy: VarianceStrategy,
    candidates: int,
) -> list[dict[str, Any]]:
    """Get variance configurations based on strategy.

    Available prompt styles:
    - parallel_first: Maximize parallelism, shallow depth
    - minimal: Essential artifacts only, fast planning
    - thorough: Complete production-ready coverage
    - modular: Clean separation of concerns
    - risk_aware: Fail-fast, validate risks early
    - default: Natural discovery baseline

    Args:
        strategy: Variance strategy to use
        candidates: Number of candidates to generate

    Returns:
        List of variance configuration dicts
    """
    if strategy == VarianceStrategy.PROMPTING:
        configs = [
            {"prompt_style": "parallel_first"},
            {"prompt_style": "minimal"},
            {"prompt_style": "thorough"},
            {"prompt_style": "modular"},
            {"prompt_style": "risk_aware"},
        ]
        return configs[:candidates]

    elif strategy == VarianceStrategy.TEMPERATURE:
        temps = [0.2, 0.3, 0.4, 0.5, 0.6][:candidates]
        return [{"temperature": t, "prompt_style": "default"} for t in temps]

    elif strategy == VarianceStrategy.CONSTRAINTS:
        return [
            {"constraint": "max_depth=2", "prompt_style": "default"},
            {"constraint": "min_leaves=5", "prompt_style": "default"},
            {"constraint": "max_artifacts=8", "prompt_style": "default"},
            {"constraint": "no_bottlenecks", "prompt_style": "default"},
            {"constraint": None, "prompt_style": "default"},
        ][:candidates]

    elif strategy == VarianceStrategy.MIXED:
        return [
            {"prompt_style": "parallel_first"},
            {"prompt_style": "thorough", "temperature": 0.4},
            {"prompt_style": "modular"},
            {"prompt_style": "risk_aware", "temperature": 0.3},
            {"prompt_style": "minimal", "temperature": 0.5},
        ][:candidates]

    else:
        # Default: mix of strategies
        return [{"prompt_style": "default"}] * candidates


def apply_variance(goal: str, config: dict[str, Any]) -> str:
    """Apply variance configuration to the goal prompt.

    Args:
        goal: Original goal string
        config: Variance configuration dict

    Returns:
        Varied goal prompt
    """
    prompt_style = config.get("prompt_style", "default")
    variance_prompt = VARIANCE_PROMPTS.get(prompt_style, VARIANCE_PROMPTS["default"])

    # Add constraint if present
    constraint = config.get("constraint")
    constraint_text = ""
    if constraint:
        constraint_text = f"\n\nCONSTRAINT: {constraint}"

    return f"{goal}\n\n{variance_prompt}{constraint_text}"
