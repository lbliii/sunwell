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
from typing import TYPE_CHECKING, Any

from sunwell.models import ModelProtocol
from sunwell.planning.routing.decision import RoutingDecision
from sunwell.planning.routing.exemplars import match_exemplar
from sunwell.planning.routing.rubric import DEFAULT_RUBRIC
from sunwell.planning.routing.types import (
    Complexity,
    ExecutionTier,
    Intent,
    UserExpertise,
    UserMood,
    determine_tier,
)

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.planning.skills.types import Skill


# Pre-compiled regex pattern for JSON extraction (avoid per-call compilation)
_RE_JSON_OBJECT = re.compile(r'\{[^{}]*\}', re.DOTALL)


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
        from sunwell.models import GenerateOptions

        # Step 1: Match exemplar for confidence calibration
        matched_exemplar, exemplar_similarity = match_exemplar(request)

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
        tier = determine_tier(final_confidence, has_shortcut)

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
            # Don't mark as TRIVIAL if explanation needed
            is_question = any(
                kw in lower
                for kw in ["how to", "how do", "what ", "create ", "build ", "write ", "make "]
            )
            is_explanation_needed = intent == Intent.EXPLAIN or is_question
            if not is_explanation_needed:
                complexity = Complexity.TRIVIAL

        # Mood detection
        mood = UserMood.NEUTRAL
        upper_count = sum(1 for c in request if c.isupper())
        if any(c.isupper() for c in request) and upper_count > len(request) * 0.3:
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
        from sunwell.models import OllamaModel

        model = OllamaModel(model=model_name)

    return UnifiedRouter(
        model=model,
        cache_size=cache_size,
        available_lenses=available_lenses or [],
    )
