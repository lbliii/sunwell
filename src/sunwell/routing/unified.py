"""Unified Router - RFC-030 Single-Model Routing Architecture.

Replaces fragmented routing systems with a single tiny model that handles
ALL pre-processing decisions in one inference call:

1. Intent Classification — What kind of task is this?
2. Complexity Assessment — How complex is this task?
3. Lens Selection — Which lens should handle it?
4. Tool Prediction — What tools might be needed?
5. User Mood Detection — What's the user's emotional state?
6. Expertise Level — What's the user's technical level?
7. Skill Suggestions — RFC-070: Which skills match the intent? (NEW)

Benefits:
- One model config, one loaded model, one inference per request
- Thread-safe O(1) LRU cache for repeated queries (RFC-094)
- Graceful fallback to heuristics if model fails
- Backward-compatible adapter for CognitiveRouter consumers
- RFC-070: Automatic skill discovery via trigger matching

See: RFC-030-unified-router.md, RFC-070-dori-lens-migration.md, RFC-094
"""


import asyncio
import dataclasses
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.models.protocol import ModelProtocol

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.skills.types import Skill


# Pre-compiled regex pattern for JSON extraction (avoid per-call compilation)
_RE_JSON_OBJECT = re.compile(r'\{[^{}]*\}', re.DOTALL)

# =============================================================================
# Intent Taxonomy (RFC-030)
# =============================================================================


class Intent(str, Enum):
    """Primary intent for task classification.

    Simplified from CognitiveRouter's 8 intents to 6 core intents
    that align with common user patterns.
    """

    CODE = "code"           # Write, modify, or generate code
    EXPLAIN = "explain"     # Explain concepts, code, or decisions
    DEBUG = "debug"         # Fix bugs, troubleshoot errors
    CHAT = "chat"           # Casual conversation, greetings
    SEARCH = "search"       # Find information, explore codebase
    REVIEW = "review"       # Review code, audit, analyze


class Complexity(str, Enum):
    """Task complexity levels."""

    TRIVIAL = "trivial"     # Single-file, obvious change
    STANDARD = "standard"   # Multi-file, typical task
    COMPLEX = "complex"     # Multi-faceted, needs planning


class UserMood(str, Enum):
    """Detected user emotional state.

    Affects response tone and verbosity.
    """

    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"  # ALL CAPS, urgency markers
    CURIOUS = "curious"        # Questions, exploration
    RUSHED = "rushed"          # Time pressure indicators
    CONFUSED = "confused"      # Uncertainty markers


class UserExpertise(str, Enum):
    """Detected user expertise level.

    Affects explanation depth and assumed knowledge.
    """

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


# =============================================================================
# Confidence Rubric (RFC-022 Enhancement)
# =============================================================================

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
                reasons.append(f"+{self.exemplar_match_high} high exemplar match ({exemplar_similarity:.2f})")
            elif exemplar_similarity > 0.7:
                score += self.exemplar_match_mod
                reasons.append(f"+{self.exemplar_match_mod} moderate exemplar match ({exemplar_similarity:.2f})")
            elif exemplar_similarity < 0.5:
                score += self.no_exemplar_match  # Negative
                reasons.append(f"{self.no_exemplar_match} low exemplar match ({exemplar_similarity:.2f})")

        # Clamp to 0-100
        score = max(0, min(100, score))

        explanation = f"Base {self.base_score}: " + ", ".join(reasons) if reasons else f"Base {self.base_score}"
        return score, explanation

    def to_confidence_level(self, score: int) -> str:
        """Convert score to confidence level string."""
        if score >= 80:
            return "HIGH"
        elif score >= 60:
            return "MEDIUM"
        else:
            return "LOW"

    def score_to_tier(self, score: int, has_shortcut: bool) -> "ExecutionTier":
        """Determine execution tier from confidence score."""
        if has_shortcut or score >= 85:
            return ExecutionTier.FAST
        elif score >= 60:
            return ExecutionTier.LIGHT
        else:
            return ExecutionTier.FULL


# =============================================================================
# Execution Tiers (RFC-022 Enhancement)
# =============================================================================


class ExecutionTier(int, Enum):
    """Execution tiers for adaptive response depth.

    Higher confidence → faster, lighter response.
    Lower confidence → more reasoning, possible confirmation.
    """

    FAST = 0    # No analysis, direct dispatch, ~50ms
    LIGHT = 1   # Brief acknowledgment, auto-proceed, ~200ms
    FULL = 2    # Full CoT reasoning, confirmation required, ~500ms


@dataclass(frozen=True, slots=True)
class TierBehavior:
    """Behavior configuration for each execution tier.

    Affects how the agent responds based on routing confidence.
    """

    show_reasoning: bool
    """Whether to show chain-of-thought reasoning."""

    require_confirmation: bool
    """Whether to ask for confirmation before proceeding."""

    output_format: str  # "compact" | "standard" | "detailed"
    """Verbosity of the response."""

    @classmethod
    def for_tier(cls, tier: ExecutionTier) -> "TierBehavior":
        """Get behavior configuration for a tier."""
        behaviors = {
            ExecutionTier.FAST: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="compact",
            ),
            ExecutionTier.LIGHT: cls(
                show_reasoning=False,
                require_confirmation=False,
                output_format="standard",
            ),
            ExecutionTier.FULL: cls(
                show_reasoning=True,
                require_confirmation=True,
                output_format="detailed",
            ),
        }
        return behaviors[tier]


def _determine_tier(confidence: float, has_shortcut: bool) -> ExecutionTier:
    """Determine execution tier from confidence score.

    Args:
        confidence: 0.0-1.0 confidence score
        has_shortcut: Whether request is an explicit shortcut (::command)

    Returns:
        ExecutionTier for the given confidence level
    """
    if has_shortcut or confidence >= 0.85:
        return ExecutionTier.FAST
    elif confidence >= 0.60:
        return ExecutionTier.LIGHT
    else:
        return ExecutionTier.FULL


# =============================================================================
# Routing Exemplars (RFC-022 Enhancement)
# =============================================================================


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
        reasoning="Goal: find bugs | Scope: single file | AMBIGUOUS - bugs could mean logic, security, edge cases",
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


def _match_exemplar(task: str, exemplars: tuple[RoutingExemplar, ...] = ROUTING_EXEMPLARS) -> tuple[RoutingExemplar | None, float]:
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


# Default rubric instance
DEFAULT_RUBRIC = ConfidenceRubric()


# =============================================================================
# Routing Decision (RFC-030)
# =============================================================================


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """All routing decisions in one immutable struct.

    This is the unified output from the router, replacing:
    - CognitiveRouter's RoutingDecision (intent, lens, focus)
    - TieredAttunement's AttunementResult (tier, confidence)
    - Discernment's quick validation (confidence gating)
    - Mirror's mood/expertise detection

    Thread-safe: Immutable (frozen=True) + no mutable defaults.
    """

    intent: Intent
    complexity: Complexity
    lens: str | None                    # Selected lens (None = no specific lens)
    tools: tuple[str, ...]              # Predicted tools: file_read, file_write, search, terminal
    mood: UserMood
    expertise: UserExpertise
    confidence: float                   # 0.0-1.0 routing confidence
    reasoning: str                      # One-sentence explanation

    # Retrieval hints (derived from intent)
    focus: tuple[str, ...] = ()         # Keywords for retrieval boosting
    secondary_lenses: tuple[str, ...] = ()

    # RFC-070: Skill suggestions based on trigger matching
    suggested_skills: tuple[str, ...] = ()
    """Skills whose triggers match the input."""

    skill_confidence: float = 0.0
    """Confidence in skill suggestions (0.0-1.0)."""

    # RFC-022 Enhancement: Deterministic confidence
    confidence_breakdown: str = ""
    """Explanation of how confidence was calculated."""

    matched_exemplar: str | None = None
    """Name of matched routing exemplar, if any."""

    rubric_confidence: float | None = None
    """Confidence from deterministic rubric (0-1), if calculated."""

    # RFC-022 Enhancement: Tiered execution
    tier: ExecutionTier = ExecutionTier.LIGHT
    """Execution tier based on confidence."""

    @property
    def behavior(self) -> TierBehavior:
        """Get behavior configuration for this decision's tier."""
        return TierBehavior.for_tier(self.tier)

    @property
    def top_k(self) -> int:
        """Retrieval depth based on complexity."""
        return {
            Complexity.TRIVIAL: 3,
            Complexity.STANDARD: 5,
            Complexity.COMPLEX: 8,
        }.get(self.complexity, 5)

    @property
    def threshold(self) -> float:
        """Retrieval threshold based on complexity."""
        return {
            Complexity.TRIVIAL: 0.4,
            Complexity.STANDARD: 0.3,
            Complexity.COMPLEX: 0.2,
        }.get(self.complexity, 0.3)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent.value,
            "complexity": self.complexity.value,
            "lens": self.lens,
            "tools": list(self.tools),
            "mood": self.mood.value,
            "expertise": self.expertise.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "focus": list(self.focus),
            "secondary_lenses": list(self.secondary_lenses),
            "suggested_skills": list(self.suggested_skills),
            "skill_confidence": self.skill_confidence,
            "confidence_breakdown": self.confidence_breakdown,
            "matched_exemplar": self.matched_exemplar,
            "rubric_confidence": self.rubric_confidence,
            "tier": self.tier.value,
            "top_k": self.top_k,
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingDecision:
        """Create from dictionary."""
        return cls(
            intent=Intent(data.get("intent", "code")),
            complexity=Complexity(data.get("complexity", "standard")),
            lens=data.get("lens"),
            tools=tuple(data.get("tools", [])),
            mood=UserMood(data.get("mood", "neutral")),
            expertise=UserExpertise(data.get("expertise", "intermediate")),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
            focus=tuple(data.get("focus", [])),
            secondary_lenses=tuple(data.get("secondary_lenses", [])),
            suggested_skills=tuple(data.get("suggested_skills", [])),
            skill_confidence=float(data.get("skill_confidence", 0.0)),
            confidence_breakdown=data.get("confidence_breakdown", ""),
            matched_exemplar=data.get("matched_exemplar"),
            rubric_confidence=data.get("rubric_confidence"),
            tier=ExecutionTier(data.get("tier", 1)),
        )


# =============================================================================
# Unified Router Prompt
# =============================================================================


UNIFIED_ROUTER_PROMPT = '''Analyze this request and respond with JSON only.

Request: "{request}"
Context: {context}

{{
  "intent": "code|explain|debug|chat|search|review",
  "complexity": "trivial|standard|complex",
  "lens": "coder|writer|reviewer|helper|null",
  "tools": ["file_read", "file_write", "search", "terminal"] or [],
  "mood": "neutral|frustrated|curious|rushed|confused",
  "expertise": "beginner|intermediate|expert",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence"
}}'''


# Lens name mapping (short names from prompt → full lens names)
LENS_NAME_MAP = {
    "coder": "coder",
    "writer": "tech-writer",
    "reviewer": "code-reviewer",
    "helper": "helper",
    "null": None,
    None: None,
}

# Intent → default lens mapping
INTENT_LENS_MAP = {
    Intent.CODE: "coder",
    Intent.EXPLAIN: "tech-writer",
    Intent.DEBUG: "code-reviewer",
    Intent.CHAT: "helper",
    Intent.SEARCH: "helper",
    Intent.REVIEW: "code-reviewer",
}

# Intent → focus keywords
INTENT_FOCUS_MAP = {
    Intent.CODE: ("implementation", "patterns", "code"),
    Intent.EXPLAIN: ("concepts", "documentation", "examples"),
    Intent.DEBUG: ("errors", "debugging", "troubleshooting"),
    Intent.CHAT: (),
    Intent.SEARCH: ("search", "find", "locate"),
    Intent.REVIEW: ("review", "quality", "issues"),
}


# =============================================================================
# Unified Router Implementation (RFC-030)
# =============================================================================


@dataclass(slots=True)
class UnifiedRouter:
    """One tiny model for ALL routing decisions.

    Thread-safe caching with double-checked locking pattern (Python 3.14t safe).
    Uses OrderedDict for O(1) LRU operations (RFC-094).

    RFC-070: Now includes skill suggestion via trigger matching.

    Usage:
        router = UnifiedRouter(model=OllamaModel("qwen2.5:1.5b"))
        decision = await router.route("fix the bug in auth.py")

        # decision.intent = Intent.DEBUG
        # decision.complexity = Complexity.TRIVIAL
        # decision.lens = "code-reviewer"
        # decision.mood = UserMood.NEUTRAL
        # decision.confidence = 0.85

        # RFC-070: With lens for skill matching
        decision = await router.route("audit the documentation", lens=tech_writer_lens)
        # decision.suggested_skills = ("audit-documentation",)
        # decision.skill_confidence = 0.9

    Configuration:
        - model: The tiny model for routing (qwen2.5:1.5b recommended)
        - cache_size: LRU cache size (default 1000)
        - temperature: Model temperature (default 0.1 for consistency)
        - available_lenses: Optional list to validate lens selection
    """

    model: ModelProtocol
    cache_size: int = 1000
    temperature: float = 0.1
    available_lenses: list[str] = field(default_factory=list)

    # Private state with thread safety — OrderedDict for O(1) LRU (RFC-094)
    _cache: OrderedDict[int, RoutingDecision] = field(default_factory=OrderedDict, repr=False)
    _sync_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _async_lock: asyncio.Lock | None = field(default=None, repr=False)
    _history: list[tuple[str, RoutingDecision]] = field(default_factory=list, repr=False)

    async def route(
        self,
        request: str,
        context: dict[str, Any] | None = None,
        lens: Lens | None = None,
    ) -> RoutingDecision:
        """Single inference call returns all routing decisions.

        RFC-070: Now supports skill suggestion via lens trigger matching.

        Args:
            request: The user's request/task
            context: Optional context (file info, code snippet, etc.)
            lens: Optional lens for skill trigger matching (RFC-070)

        Returns:
            RoutingDecision with all routing information including suggested_skills
        """
        # RFC-070: Check for shortcut commands first
        if lens and lens.router and lens.router.shortcuts:
            shortcut_result = self._check_shortcut(request, lens)
            if shortcut_result:
                return shortcut_result

        # Compute cache key (include lens name for skill matching)
        lens_name = lens.metadata.name if lens else None
        context_items = tuple(sorted((context or {}).items()))
        cache_key = hash((request, context_items, lens_name))

        # Fast path: check cache without lock
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Initialize async lock lazily (can't be done at dataclass creation)
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        # Slow path: acquire async lock for compute, sync lock for cache update
        async with self._async_lock:
            # Double-check after acquiring lock
            if cache_key in self._cache:
                return self._cache[cache_key]

            try:
                decision = await self._compute_decision(request, context)
            except Exception as e:
                # Fallback to heuristics on any error
                decision = self.fallback_decision(request, error=str(e))

            # RFC-070: Match skill triggers if lens provided
            if lens and lens.skills:
                suggested, confidence = self._match_skill_triggers(request, lens.skills)
                decision = dataclasses.replace(
                    decision,
                    suggested_skills=suggested,
                    skill_confidence=confidence,
                )

            # Use sync lock for cache mutation (quick, no await)
            with self._sync_lock:
                # LRU eviction if cache full — O(1) with OrderedDict (RFC-094)
                while len(self._cache) >= self.cache_size:
                    self._cache.popitem(last=False)

                self._cache[cache_key] = decision

                # Record for history
                self._history.append((request, decision))

            return decision

    def _check_shortcut(self, request: str, lens: Lens) -> RoutingDecision | None:
        """Check if request is a shortcut command.

        RFC-070: Returns a pre-built decision for shortcut commands like "::a".
        """
        if not lens.router or not lens.router.shortcuts:
            return None

        request_stripped = request.strip()

        # Check for exact shortcut match
        if request_stripped in lens.router.shortcuts:
            skill_name = lens.router.shortcuts[request_stripped]
            return RoutingDecision(
                intent=Intent.CODE,  # Skills are action-oriented
                complexity=Complexity.STANDARD,
                lens=lens.metadata.name,
                tools=(),
                mood=UserMood.NEUTRAL,
                expertise=UserExpertise.INTERMEDIATE,
                confidence=1.0,
                reasoning=f"Shortcut '{request_stripped}' → skill '{skill_name}'",
                suggested_skills=(skill_name,),
                skill_confidence=1.0,
                # RFC-022: Shortcuts are deterministic, highest confidence
                confidence_breakdown="Explicit shortcut: +20 (deterministic)",
                rubric_confidence=1.0,
                tier=ExecutionTier.FAST,
            )

        return None

    def _match_skill_triggers(
        self,
        request: str,
        skills: tuple[Skill, ...],
    ) -> tuple[tuple[str, ...], float]:
        """Find skills whose triggers match the input.

        RFC-070: Matches request against skill triggers for automatic discovery.

        Returns:
            Tuple of (matched skill names, confidence score)
        """
        request_lower = request.lower()
        matches: list[tuple[str, int]] = []  # (skill_name, match_count)

        for skill in skills:
            if not skill.triggers:
                continue

            match_count = sum(1 for trigger in skill.triggers if trigger.lower() in request_lower)
            if match_count > 0:
                matches.append((skill.name, match_count))

        if not matches:
            return (), 0.0

        # Sort by match count (descending) and take top matches
        matches.sort(key=lambda x: x[1], reverse=True)

        # Compute confidence based on match quality
        # Scale: 1 trigger = 33%, 2 = 67%, 3+ = 100%
        best_match_count = matches[0][1] if matches else 0
        confidence = min(1.0, best_match_count / 3)

        return tuple(m[0] for m in matches), confidence

    async def _compute_decision(
        self,
        request: str,
        context: dict[str, Any] | None,
    ) -> RoutingDecision:
        """Compute routing decision via model inference.

        RFC-022 Enhancement: Also calculates deterministic rubric confidence
        and matches against exemplars for calibration.
        """
        from sunwell.models.protocol import GenerateOptions

        # Step 1: Match exemplar for confidence calibration
        matched_exemplar, exemplar_similarity = _match_exemplar(request)

        # Step 2: Calculate rubric-based confidence
        rubric_score, confidence_breakdown = DEFAULT_RUBRIC.calculate(
            request, context, exemplar_similarity
        )
        rubric_confidence = rubric_score / 100.0  # Normalize to 0-1

        # Step 3: Get LLM routing decision
        prompt = UNIFIED_ROUTER_PROMPT.format(
            request=request,
            context=json.dumps(context) if context else "{}",
        )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=self.temperature),
        )

        decision = self._parse_decision(result.content or "", request)

        # Step 4: Enhance decision with rubric scoring
        # Use higher of: LLM confidence, rubric confidence
        final_confidence = max(decision.confidence, rubric_confidence)

        # Step 5: Determine execution tier based on confidence
        has_shortcut = request.strip().startswith("::")
        tier = _determine_tier(final_confidence, has_shortcut)

        return dataclasses.replace(
            decision,
            confidence=final_confidence,
            confidence_breakdown=confidence_breakdown,
            matched_exemplar=matched_exemplar.input if matched_exemplar else None,
            rubric_confidence=rubric_confidence,
            tier=tier,
        )

    def _parse_decision(self, content: str, request: str) -> RoutingDecision:
        """Parse JSON response into RoutingDecision.

        Handles various model output formats:
        - Raw JSON
        - Markdown code blocks (```json ... ```)
        - Extra text before/after JSON
        """
        # Extract JSON from various formats
        json_str = content.strip()

        # Handle markdown code blocks
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts[1:]:  # Skip text before first ```
                clean = part.strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
                if clean.startswith("{"):
                    json_str = clean.split("```")[0].strip()
                    break

        # Try to find JSON object (pre-compiled pattern)
        json_match = _RE_JSON_OBJECT.search(json_str)
        if json_match:
            json_str = json_match.group(0)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # If JSON parsing fails, use heuristic fallback
            return self.fallback_decision(request, error="JSON parse failed")

        # Parse intent
        intent_str = data.get("intent", "code").lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            # Map common variants
            intent_map = {
                "bug_fixing": Intent.DEBUG,
                "debugging": Intent.DEBUG,
                "code_generation": Intent.CODE,
                "documentation": Intent.EXPLAIN,
                "explanation": Intent.EXPLAIN,
                "code_review": Intent.REVIEW,
                "analysis": Intent.REVIEW,
            }
            intent = intent_map.get(intent_str, Intent.CODE)

        # Parse complexity
        complexity_str = data.get("complexity", "standard").lower()
        try:
            complexity = Complexity(complexity_str)
        except ValueError:
            # Map common variants
            complexity_map = {
                "simple": Complexity.TRIVIAL,
                "moderate": Complexity.STANDARD,
            }
            complexity = complexity_map.get(complexity_str, Complexity.STANDARD)

        # Parse lens
        lens_raw = data.get("lens")
        lens = LENS_NAME_MAP.get(lens_raw, lens_raw)

        # Validate lens against available lenses
        if self.available_lenses and lens and lens not in self.available_lenses:
            # Try to find a match
            for avail in self.available_lenses:
                if lens.lower() in avail.lower() or avail.lower() in lens.lower():
                    lens = avail
                    break
            else:
                # Use intent-based default
                lens = INTENT_LENS_MAP.get(intent, "helper")

        # Parse tools
        tools_raw = data.get("tools", [])
        tools = tuple(str(t) for t in tools_raw) if isinstance(tools_raw, list) else ()

        # Parse mood
        mood_str = data.get("mood", "neutral").lower()
        try:
            mood = UserMood(mood_str)
        except ValueError:
            mood = UserMood.NEUTRAL

        # Parse expertise
        expertise_str = data.get("expertise", "intermediate").lower()
        try:
            expertise = UserExpertise(expertise_str)
        except ValueError:
            expertise = UserExpertise.INTERMEDIATE

        # Parse confidence
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

        # Get reasoning
        reasoning = data.get("reasoning", "")

        # Compute focus keywords from intent
        focus = INTENT_FOCUS_MAP.get(intent, ())

        return RoutingDecision(
            intent=intent,
            complexity=complexity,
            lens=lens,
            tools=tools,
            mood=mood,
            expertise=expertise,
            confidence=confidence,
            reasoning=reasoning,
            focus=focus,
        )

    @staticmethod
    def fallback_decision(request: str, error: str | None = None) -> RoutingDecision:
        """Heuristic fallback if model fails.

        Simple keyword-based routing that ensures the system
        degrades gracefully without complete failure.
        """
        lower = request.lower()

        # Intent detection via keywords (order matters - more specific first)
        intent = Intent.CODE
        if any(kw in lower for kw in ["explain", "what is", "how does", "why"]):
            intent = Intent.EXPLAIN
        elif any(kw in lower for kw in ["fix", "bug", "error", "debug", "broken", "crash"]):
            intent = Intent.DEBUG
        elif any(kw in lower for kw in ["review", "check", "audit", "analyze"]):
            intent = Intent.REVIEW
        elif any(kw in lower for kw in ["find", "search", "where", "locate"]):
            intent = Intent.SEARCH
        elif any(kw in lower for kw in ["hey", "hi", "hello", "how are", "thanks"]):
            intent = Intent.CHAT

        # Complexity from keywords first (takes priority over length)
        complexity = Complexity.STANDARD
        if any(kw in lower for kw in ["refactor", "redesign", "migrate", "entire", "all"]):
            complexity = Complexity.COMPLEX
        elif len(request) < 50:
            # Don't mark as TRIVIAL if:
            # 1. Intent is EXPLAIN (questions need full answers)
            # 2. Contains question indicators (how to, what, create, build, write)
            # 3. Looks like a documentation/educational task
            is_question = any(kw in lower for kw in ["how to", "how do", "what ", "create ", "build ", "write ", "make "])
            is_explanation_needed = intent == Intent.EXPLAIN or is_question
            if not is_explanation_needed:
                complexity = Complexity.TRIVIAL

        # Mood detection
        mood = UserMood.NEUTRAL
        if any(c.isupper() for c in request) and sum(1 for c in request if c.isupper()) > len(request) * 0.3:
            mood = UserMood.FRUSTRATED
        elif "?" in request and any(kw in lower for kw in ["how", "what", "why"]):
            mood = UserMood.CURIOUS
        elif any(kw in lower for kw in ["asap", "urgent", "now", "quick", "fast"]):
            mood = UserMood.RUSHED
        elif any(kw in lower for kw in ["confused", "don't understand", "not sure"]):
            mood = UserMood.CONFUSED

        # Default lens based on intent
        lens = INTENT_LENS_MAP.get(intent, "helper")

        # Focus keywords
        focus = INTENT_FOCUS_MAP.get(intent, ())

        reasoning = "Heuristic fallback"
        if error:
            reasoning += f" ({error[:50]})"

        return RoutingDecision(
            intent=intent,
            complexity=complexity,
            lens=lens,
            tools=(),
            mood=mood,
            expertise=UserExpertise.INTERMEDIATE,
            confidence=0.3,  # Low confidence for fallback
            reasoning=reasoning,
            focus=focus,
        )

    def clear_cache(self) -> None:
        """Clear the routing cache."""
        with self._sync_lock:
            self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        with self._sync_lock:
            if not self._history:
                return {
                    "total_routes": 0,
                    "cache_size": len(self._cache),
                    "avg_confidence": 0.0,
                    "intent_distribution": {},
                    "mood_distribution": {},
                }

            confidences = [d.confidence for _, d in self._history]
            intents = [d.intent.value for _, d in self._history]
            moods = [d.mood.value for _, d in self._history]

            intent_counts: dict[str, int] = {}
            for i in intents:
                intent_counts[i] = intent_counts.get(i, 0) + 1

            mood_counts: dict[str, int] = {}
            for m in moods:
                mood_counts[m] = mood_counts.get(m, 0) + 1

            return {
                "total_routes": len(self._history),
                "cache_size": len(self._cache),
                "cache_hit_rate": 1 - (len(self._history) / max(1, len(self._cache))),
                "avg_confidence": sum(confidences) / len(confidences),
                "intent_distribution": intent_counts,
                "mood_distribution": mood_counts,
            }


# =============================================================================
# Factory Function
# =============================================================================


def create_unified_router(
    model: ModelProtocol | None = None,
    model_name: str = "qwen2.5:1.5b",
    cache_size: int = 1000,
    available_lenses: list[str] | None = None,
) -> UnifiedRouter:
    """Create a UnifiedRouter with sensible defaults.

    Args:
        model: Pre-configured model (takes priority)
        model_name: Ollama model name if model not provided
        cache_size: LRU cache size
        available_lenses: List of available lens names for validation

    Returns:
        Configured UnifiedRouter instance
    """
    if model is None:
        from sunwell.models.ollama import OllamaModel
        model = OllamaModel(model=model_name)

    return UnifiedRouter(
        model=model,
        cache_size=cache_size,
        available_lenses=available_lenses or [],
    )
