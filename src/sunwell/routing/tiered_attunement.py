"""Tiered Attunement - RFC-022 Enhanced Cognitive Routing.

Extends RFC-020 CognitiveRouter with DORI-inspired techniques:
1. Tiered Execution — Fast/Light/Full modes based on confidence
2. Few-Shot Exemplars — Gold-standard routing examples
3. Calibrated Confidence — Explicit scoring rubric (not LLM vibes)
4. Self-Verification — Catch routing errors before dispatch
5. Anti-Pattern Detection — Avoid known routing mistakes

This bridges the gap between Sunwell (portable) and DORI (intelligent).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sunwell.routing.cognitive_router import (
    CognitiveRouter,
    Complexity,
    Intent,
    RoutingDecision,
)

# =============================================================================
# Tier System (RFC-022)
# =============================================================================


class Tier(int, Enum):
    """Execution tiers for routing decisions."""

    FAST = 0    # No analysis, direct dispatch, ~50ms
    LIGHT = 1   # Brief acknowledgment, auto-proceed, ~200ms
    FULL = 2    # Full CoT reasoning, confirmation required, ~500ms


@dataclass
class TierBehavior:
    """Behavior configuration for each tier."""

    show_reasoning: bool
    require_confirmation: bool
    output_format: str  # compact | standard | detailed

    @classmethod
    def for_tier(cls, tier: Tier) -> TierBehavior:
        """Get behavior for a tier."""
        behaviors = {
            Tier.FAST: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="compact",
            ),
            Tier.LIGHT: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="standard",
            ),
            Tier.FULL: cls(
                show_reasoning=True,
                require_confirmation=True,
                output_format="detailed",
            ),
        }
        return behaviors[tier]


# =============================================================================
# Routing Exemplars (RFC-022)
# =============================================================================


@dataclass(frozen=True)
class RoutingExemplar:
    """Gold-standard routing example for pattern matching.

    Exemplars teach the router what good routing looks like.
    They're used for:
    1. Pattern matching (find similar exemplar)
    2. Confidence calibration (similar to exemplar = high confidence)
    3. Self-verification (does decision match exemplar reasoning?)
    """

    input: str                     # User request
    context_hints: tuple[str, ...] # Expected context signals
    reasoning: str                 # Why this routing is correct
    intent: Intent                 # Correct intent
    lens: str                      # Correct lens
    focus: tuple[str, ...]         # Correct focus terms
    confidence: str                # HIGH | MEDIUM | LOW
    tier: Tier                     # Appropriate tier
    tags: tuple[str, ...]          # For retrieval matching


# Gold-standard exemplar bank
ROUTING_EXEMPLARS: tuple[RoutingExemplar, ...] = (
    # --- CODE REVIEW ---
    RoutingExemplar(
        input="review auth.py for security",
        context_hints=("file exists", "has auth code"),
        reasoning="Goal: security review | Scope: single file | Clear intent",
        intent=Intent.CODE_REVIEW,
        lens="code-reviewer",
        focus=("security", "authentication", "injection"),
        confidence="HIGH",
        tier=Tier.FAST,
        tags=("security", "review", "auth"),
    ),
    RoutingExemplar(
        input="check this for bugs",
        context_hints=("recently edited",),
        reasoning="Goal: find bugs | Scope: single file | AMBIGUOUS - bugs could mean logic, security, edge cases",
        intent=Intent.CODE_REVIEW,
        lens="code-reviewer",
        focus=("logic", "edge_cases", "error_handling"),
        confidence="MEDIUM",
        tier=Tier.LIGHT,
        tags=("bugs", "review", "check"),
    ),
    RoutingExemplar(
        input="::review @auth.py --security",
        context_hints=("explicit command",),
        reasoning="Explicit shortcut with target - deterministic routing",
        intent=Intent.CODE_REVIEW,
        lens="code-reviewer",
        focus=("security",),
        confidence="HIGH",
        tier=Tier.FAST,
        tags=("command", "review", "security"),
    ),

    # --- TESTING ---
    RoutingExemplar(
        input="write tests for the user service",
        context_hints=("no test file exists",),
        reasoning="Goal: create tests | Scope: single module | Clear intent",
        intent=Intent.TESTING,
        lens="team-qa",
        focus=("unit_tests", "coverage", "edge_cases"),
        confidence="HIGH",
        tier=Tier.LIGHT,
        tags=("test", "write", "create"),
    ),
    RoutingExemplar(
        input="add more test coverage",
        context_hints=("test file exists", "low coverage"),
        reasoning="Goal: improve coverage | Scope: unclear which tests | Moderate ambiguity",
        intent=Intent.TESTING,
        lens="team-qa",
        focus=("coverage", "edge_cases", "branches"),
        confidence="MEDIUM",
        tier=Tier.LIGHT,
        tags=("test", "coverage", "improve"),
    ),

    # --- DOCUMENTATION ---
    RoutingExemplar(
        input="document this function",
        context_hints=("cursor on function",),
        reasoning="Goal: add docs | Scope: single function | Clear target",
        intent=Intent.DOCUMENTATION,
        lens="tech-writer",
        focus=("docstring", "parameters", "examples"),
        confidence="HIGH",
        tier=Tier.FAST,
        tags=("document", "docstring", "function"),
    ),
    RoutingExemplar(
        input="write a README for this project",
        context_hints=("no README exists",),
        reasoning="Goal: create README | Scope: project-level | Clear but broad",
        intent=Intent.DOCUMENTATION,
        lens="tech-writer",
        focus=("readme", "overview", "installation", "usage"),
        confidence="HIGH",
        tier=Tier.LIGHT,
        tags=("readme", "documentation", "project"),
    ),

    # --- REFACTORING ---
    RoutingExemplar(
        input="make this code cleaner",
        context_hints=("file focused",),
        reasoning="Goal: improve code quality | Scope: single file | Vague 'cleaner'",
        intent=Intent.REFACTORING,
        lens="code-reviewer",
        focus=("clean_code", "patterns", "readability"),
        confidence="MEDIUM",
        tier=Tier.LIGHT,
        tags=("refactor", "clean", "improve"),
    ),
    RoutingExemplar(
        input="extract this into a separate function",
        context_hints=("code selected",),
        reasoning="Goal: extract function | Scope: selection | Clear action",
        intent=Intent.REFACTORING,
        lens="code-reviewer",
        focus=("extraction", "functions", "modularity"),
        confidence="HIGH",
        tier=Tier.FAST,
        tags=("extract", "refactor", "function"),
    ),

    # --- AMBIGUOUS ---
    RoutingExemplar(
        input="help with this code",
        context_hints=(),
        reasoning="Goal: UNCLEAR | Scope: unclear | No specific ask - could be review, explain, improve, document",
        intent=Intent.UNKNOWN,
        lens="helper",
        focus=(),
        confidence="LOW",
        tier=Tier.FULL,
        tags=("help", "unclear", "ambiguous"),
    ),
    RoutingExemplar(
        input="fix this",
        context_hints=("error visible",),
        reasoning="Goal: fix something | Scope: unclear what | 'Fix' is ambiguous - validate first",
        intent=Intent.DEBUGGING,
        lens="code-reviewer",
        focus=("error", "fix", "debug"),
        confidence="MEDIUM",
        tier=Tier.LIGHT,
        tags=("fix", "error", "debug"),
    ),

    # --- ANALYSIS ---
    RoutingExemplar(
        input="explain how this authentication flow works",
        context_hints=("auth code visible",),
        reasoning="Goal: understand code | Scope: auth flow | Clear explanation request",
        intent=Intent.EXPLANATION,
        lens="tech-writer",
        focus=("authentication", "flow", "explanation"),
        confidence="HIGH",
        tier=Tier.LIGHT,
        tags=("explain", "auth", "flow"),
    ),
    RoutingExemplar(
        input="what does this function do?",
        context_hints=("function focused",),
        reasoning="Goal: explain function | Scope: single function | Simple question",
        intent=Intent.EXPLANATION,
        lens="tech-writer",
        focus=("explanation", "function", "purpose"),
        confidence="HIGH",
        tier=Tier.FAST,
        tags=("what", "explain", "function"),
    ),
)


# =============================================================================
# Calibrated Confidence Rubric (RFC-022)
# =============================================================================


@dataclass
class ConfidenceRubric:
    """Explicit confidence scoring rubric.

    Replaces LLM "vibes" with deterministic scoring.
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

    # Action verbs
    CLEAR_VERBS = frozenset({
        "review", "audit", "check", "validate",
        "test", "write", "create", "add",
        "document", "explain", "describe",
        "refactor", "extract", "rename",
        "debug", "trace", "profile",
    })

    AMBIGUOUS_VERBS = frozenset({
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
        has_file = context and context.get("file") or context and context.get("focused_file")
        file_in_task = bool(re.search(r'\b\w+\.(py|js|ts|md|yaml|json)\b', task))

        if has_file or file_in_task:
            score += self.single_file_target
            reasons.append(f"+{self.single_file_target} file target")
        elif not has_file and not file_in_task:
            score += self.no_file_context  # Negative
            reasons.append(f"{self.no_file_context} no file context")

        # Check multi-file scope
        file_matches = re.findall(r'\b\w+\.(py|js|ts|md|yaml|json)\b', task)
        if len(file_matches) > 1:
            score += self.multi_file_scope  # Negative
            reasons.append(f"{self.multi_file_scope} multi-file scope")

        # Check exemplar similarity
        if exemplar_similarity is not None:
            if exemplar_similarity > 0.85:
                score += self.exemplar_match_high
                reasons.append(f"+{self.exemplar_match_high} high exemplar match ({exemplar_similarity:.2f})")
            elif exemplar_similarity > 0.7:
                score += self.exemplar_match_mod
                reasons.append(f"+{self.exemplar_match_mod} moderate exemplar match ({exemplar_similarity:.2f})")
            elif exemplar_similarity < 0.5:
                score += self.no_exemplar_match  # Negative
                reasons.append(f"{self.no_exemplar_match} low exemplar match ({exemplar_similarity:.2f})")

        # Clamp to 0-100
        score = max(0, min(100, score))

        return score, " | ".join(reasons)

    def to_confidence_level(self, score: int) -> str:
        """Convert numeric score to confidence level."""
        if score >= 80:
            return "HIGH"
        elif score >= 50:
            return "MEDIUM"
        else:
            return "LOW"

    def score_to_tier(self, score: int, has_explicit_shortcut: bool) -> Tier:
        """Determine appropriate tier from confidence score."""
        if has_explicit_shortcut and score >= 80:
            return Tier.FAST
        elif score >= 65:
            return Tier.LIGHT
        else:
            return Tier.FULL


# =============================================================================
# Self-Verification (RFC-022)
# =============================================================================


@dataclass
class VerificationResult:
    """Result of self-verification check."""

    passed: bool
    action: str  # proceed | escalate | clarify
    red_flags: list[str] = field(default_factory=list)
    adjusted_confidence: str | None = None

    def should_escalate(self) -> bool:
        """Check if we should escalate to higher tier."""
        return self.action == "escalate"

    def should_clarify(self) -> bool:
        """Check if we should ask user for clarification."""
        return self.action == "clarify"


# Anti-patterns to check against
ANTI_PATTERNS: dict[str, dict[str, Any]] = {
    "review_empty": {
        "check": lambda task, ctx, dec: (
            dec.intent == Intent.CODE_REVIEW and
            ctx and ctx.get("file_state") == "empty"
        ),
        "message": "Cannot review empty file - should be CREATION task",
        "severity": "high",
    },
    "over_orchestration": {
        "check": lambda task, ctx, dec: (
            len(task.split()) < 5 and  # Very short task
            "fix" in task.lower() and
            ctx and ctx.get("single_line_change")
        ),
        "message": "Full orchestration for trivial change - use Tier 0",
        "severity": "low",
    },
    "test_without_code": {
        "check": lambda task, ctx, dec: (
            dec.intent == Intent.TESTING and
            ctx and not ctx.get("code_visible")
        ),
        "message": "Testing request without code context",
        "severity": "medium",
    },
    "document_nonexistent": {
        "check": lambda task, ctx, dec: (
            dec.intent == Intent.DOCUMENTATION and
            ctx and ctx.get("file_state") == "not_found"
        ),
        "message": "Documentation request for non-existent file",
        "severity": "high",
    },
}


def verify_routing(
    task: str,
    context: dict[str, Any] | None,
    decision: RoutingDecision,
    confidence_level: str,
) -> VerificationResult:
    """Self-verify a routing decision before dispatch.

    Checks for:
    1. Capability match - Does lens handle this intent?
    2. State match - Does file state match operation?
    3. Anti-patterns - Known routing mistakes?

    Returns:
        VerificationResult with action recommendation
    """
    red_flags: list[str] = []

    # Check anti-patterns
    for _name, pattern in ANTI_PATTERNS.items():
        try:
            if pattern["check"](task, context, decision):
                red_flags.append(f"[{pattern['severity']}] {pattern['message']}")
        except Exception:
            pass  # Skip failing checks

    # Capability match: Does lens typically handle this intent?
    LENS_CAPABILITIES = {
        "code-reviewer": {Intent.CODE_REVIEW, Intent.ANALYSIS, Intent.REFACTORING, Intent.DEBUGGING},
        "tech-writer": {Intent.DOCUMENTATION, Intent.EXPLANATION},
        "team-qa": {Intent.TESTING},
        "helper": set(Intent),  # Helper handles everything
    }

    lens_caps = LENS_CAPABILITIES.get(decision.lens, set())
    if decision.intent not in lens_caps and decision.lens != "helper":
        red_flags.append(f"Lens '{decision.lens}' doesn't typically handle intent '{decision.intent.value}'")

    # Determine action based on red flags and confidence
    if not red_flags:
        return VerificationResult(passed=True, action="proceed")

    high_severity = any("[high]" in flag for flag in red_flags)

    if high_severity:
        return VerificationResult(
            passed=False,
            action="escalate",
            red_flags=red_flags,
            adjusted_confidence="LOW",
        )
    elif confidence_level == "HIGH":
        return VerificationResult(
            passed=True,
            action="proceed",
            red_flags=red_flags,
            adjusted_confidence="MEDIUM",
        )
    elif confidence_level == "MEDIUM":
        return VerificationResult(
            passed=False,
            action="escalate",
            red_flags=red_flags,
        )
    else:
        return VerificationResult(
            passed=False,
            action="clarify",
            red_flags=red_flags,
        )


# =============================================================================
# Tiered Attunement (Main Class)
# =============================================================================


@dataclass
class AttunementResult:
    """Result from TieredAttunement routing."""

    decision: RoutingDecision
    tier: Tier
    confidence_score: int
    confidence_level: str
    confidence_explanation: str
    matched_exemplar: RoutingExemplar | None
    exemplar_similarity: float | None
    verification: VerificationResult
    behavior: TierBehavior

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision": self.decision.to_dict(),
            "tier": self.tier.value,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "confidence_explanation": self.confidence_explanation,
            "matched_exemplar": self.matched_exemplar.input if self.matched_exemplar else None,
            "exemplar_similarity": self.exemplar_similarity,
            "verification": {
                "passed": self.verification.passed,
                "action": self.verification.action,
                "red_flags": self.verification.red_flags,
            },
            "behavior": {
                "show_reasoning": self.behavior.show_reasoning,
                "require_confirmation": self.behavior.require_confirmation,
                "output_format": self.behavior.output_format,
            },
        }


@dataclass
class TieredAttunement:
    """Enhanced cognitive routing with DORI-inspired techniques.

    Wraps CognitiveRouter with:
    - Tiered execution (Fast/Light/Full)
    - Exemplar-based pattern matching
    - Calibrated confidence scoring
    - Self-verification before dispatch

    Example:
        attunement = TieredAttunement(
            router=CognitiveRouter(model, lenses),
        )

        result = await attunement.route("Review auth.py for security")
        # result.tier = Tier.FAST (explicit target + clear intent)
        # result.confidence_score = 85
        # result.verification.passed = True
    """

    router: CognitiveRouter
    exemplars: tuple[RoutingExemplar, ...] = ROUTING_EXEMPLARS
    rubric: ConfidenceRubric = field(default_factory=ConfidenceRubric)

    # Stats tracking
    _tier_counts: dict[Tier, int] = field(default_factory=lambda: dict.fromkeys(Tier, 0))
    _escalations: int = field(default=0, init=False)
    _clarifications: int = field(default=0, init=False)

    async def route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        tier_override: Tier | None = None,
    ) -> AttunementResult:
        """Route a task with tiered execution.

        Args:
            task: The task description or command
            context: Optional context (file state, recent edits, etc.)
            tier_override: Force a specific tier (--fast, --full flags)

        Returns:
            AttunementResult with full routing information
        """
        # Step 1: Match exemplar
        exemplar, similarity = self._match_exemplar(task)

        # Step 2: Calculate calibrated confidence
        conf_score, conf_explanation = self.rubric.calculate(task, context, similarity)
        conf_level = self.rubric.to_confidence_level(conf_score)

        # Step 3: Determine tier
        has_shortcut = task.strip().startswith("::")
        tier = tier_override or self.rubric.score_to_tier(conf_score, has_shortcut)

        # Step 4: Route based on tier
        if tier == Tier.FAST:
            decision = await self._route_fast(task, context, exemplar)
        elif tier == Tier.LIGHT:
            decision = await self._route_light(task, context, exemplar)
        else:
            decision = await self._route_full(task, context)

        # Step 5: Self-verify
        verification = verify_routing(task, context, decision, conf_level)

        # Step 6: Handle escalation if needed
        if verification.should_escalate() and tier != Tier.FULL:
            self._escalations += 1
            # Recursively route at higher tier
            return await self.route(task, context, tier_override=Tier.FULL)

        if verification.should_clarify():
            self._clarifications += 1

        # Update stats
        self._tier_counts[tier] += 1

        # Get behavior for this tier
        behavior = TierBehavior.for_tier(tier)

        # Adjust confidence if verification flagged issues
        if verification.adjusted_confidence:
            conf_level = verification.adjusted_confidence

        return AttunementResult(
            decision=decision,
            tier=tier,
            confidence_score=conf_score,
            confidence_level=conf_level,
            confidence_explanation=conf_explanation,
            matched_exemplar=exemplar,
            exemplar_similarity=similarity,
            verification=verification,
            behavior=behavior,
        )

    def _match_exemplar(self, task: str) -> tuple[RoutingExemplar | None, float | None]:
        """Find the most similar exemplar using keyword matching.

        Simple keyword overlap scoring (no embedding needed).
        """
        task_lower = task.lower()
        task_words = set(task_lower.split())

        best_match: RoutingExemplar | None = None
        best_score = 0.0

        for exemplar in self.exemplars:
            # Score based on tag overlap
            tag_overlap = len(set(exemplar.tags) & task_words)

            # Also check input similarity
            exemplar_words = set(exemplar.input.lower().split())
            word_overlap = len(task_words & exemplar_words)

            # Combined score (normalized)
            score = (tag_overlap * 0.6 + word_overlap * 0.4) / max(len(task_words), 1)

            if score > best_score:
                best_score = score
                best_match = exemplar

        # Normalize to 0-1 range
        similarity = min(best_score * 2, 1.0) if best_score > 0 else None

        return best_match, similarity

    async def _route_fast(
        self,
        task: str,
        context: dict[str, Any] | None,
        exemplar: RoutingExemplar | None,
    ) -> RoutingDecision:
        """Tier 0: Fast path routing.

        Uses exemplar or heuristics only - no LLM call.
        """
        # If we have a good exemplar match, use it directly
        if exemplar:
            return RoutingDecision(
                intent=exemplar.intent,
                lens=exemplar.lens,
                secondary_lenses=[],
                focus=list(exemplar.focus),
                complexity=Complexity.MODERATE,
                top_k=5,
                threshold=0.3,
                confidence=0.9 if exemplar.confidence == "HIGH" else 0.7,
                reasoning=f"Exemplar match: '{exemplar.input[:30]}...'",
            )

        # Fall back to heuristic routing
        return self.router._heuristic_fallback(task)

    async def _route_light(
        self,
        task: str,
        context: dict[str, Any] | None,
        exemplar: RoutingExemplar | None,
    ) -> RoutingDecision:
        """Tier 1: Light routing.

        Quick LLM check if available, otherwise enhanced heuristics.
        """
        # Try quick LLM route if model available
        try:
            return await self.router.route(task, context)
        except Exception:
            # Fall back to exemplar or heuristic
            return await self._route_fast(task, context, exemplar)

    async def _route_full(
        self,
        task: str,
        context: dict[str, Any] | None,
    ) -> RoutingDecision:
        """Tier 2: Full routing with CoT reasoning.

        Uses full LLM routing with detailed prompt.
        """
        return await self.router.route(task, context)

    def get_stats(self) -> dict[str, Any]:
        """Get attunement statistics."""
        total = sum(self._tier_counts.values())
        return {
            "total_routes": total,
            "tier_distribution": {
                "fast": self._tier_counts[Tier.FAST],
                "light": self._tier_counts[Tier.LIGHT],
                "full": self._tier_counts[Tier.FULL],
            },
            "fast_path_rate": self._tier_counts[Tier.FAST] / total if total > 0 else 0,
            "escalations": self._escalations,
            "clarifications": self._clarifications,
            "router_stats": self.router.get_stats(),
        }


# =============================================================================
# Convenience Factory
# =============================================================================


def create_tiered_attunement(
    router_model: Any,
    available_lenses: list[str],
) -> TieredAttunement:
    """Create a TieredAttunement with default configuration.

    Args:
        router_model: Model for LLM-based routing
        available_lenses: List of available lens names

    Returns:
        Configured TieredAttunement instance
    """
    router = CognitiveRouter(
        router_model=router_model,
        available_lenses=available_lenses,
    )

    return TieredAttunement(router=router)
