"""Unified Router - RFC-030 Single-Model Routing Architecture.

Replaces fragmented routing systems with a single tiny model that handles
ALL pre-processing decisions in one inference call:

1. Intent Classification — What kind of task is this?
2. Complexity Assessment — How complex is this task?
3. Lens Selection — Which lens should handle it?
4. Tool Prediction — What tools might be needed?
5. User Mood Detection — What's the user's emotional state?
6. Expertise Level — What's the user's technical level?

Benefits:
- One model config, one loaded model, one inference per request
- Thread-safe LRU cache for repeated queries
- Graceful fallback to heuristics if model fails
- Backward-compatible adapter for CognitiveRouter consumers

See: RFC-030-unified-router.md
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sunwell.models.protocol import ModelProtocol

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

    # Legacy compatibility fields (computed, not from model)
    focus: tuple[str, ...] = ()         # Keywords for retrieval boosting
    secondary_lenses: tuple[str, ...] = ()

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


@dataclass
class UnifiedRouter:
    """One tiny model for ALL routing decisions.

    Thread-safe caching with double-checked locking pattern (Python 3.14t safe).

    Usage:
        router = UnifiedRouter(model=OllamaModel("qwen2.5:1.5b"))
        decision = await router.route("fix the bug in auth.py")

        # decision.intent = Intent.DEBUG
        # decision.complexity = Complexity.TRIVIAL
        # decision.lens = "code-reviewer"
        # decision.mood = UserMood.NEUTRAL
        # decision.confidence = 0.85

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

    # Private state with thread safety
    _cache: dict[int, RoutingDecision] = field(default_factory=dict, repr=False)
    _cache_order: list[int] = field(default_factory=list, repr=False)  # For LRU
    _sync_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _async_lock: asyncio.Lock | None = field(default=None, repr=False)
    _history: list[tuple[str, RoutingDecision]] = field(default_factory=list, repr=False)

    async def route(
        self,
        request: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Single inference call returns all routing decisions.

        Args:
            request: The user's request/task
            context: Optional context (file info, code snippet, etc.)

        Returns:
            RoutingDecision with all routing information
        """
        # Compute cache key
        context_items = tuple(sorted((context or {}).items()))
        cache_key = hash((request, context_items))

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

            # Use sync lock for cache mutation (quick, no await)
            with self._sync_lock:
                # LRU eviction if cache full
                if len(self._cache) >= self.cache_size:
                    # Remove oldest entry
                    oldest_key = self._cache_order.pop(0)
                    del self._cache[oldest_key]

                self._cache[cache_key] = decision
                self._cache_order.append(cache_key)

                # Record for history
                self._history.append((request, decision))

            return decision

    async def _compute_decision(
        self,
        request: str,
        context: dict[str, Any] | None,
    ) -> RoutingDecision:
        """Compute routing decision via model inference."""
        from sunwell.models.protocol import GenerateOptions

        prompt = UNIFIED_ROUTER_PROMPT.format(
            request=request,
            context=json.dumps(context) if context else "{}",
        )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=self.temperature),
        )

        return self._parse_decision(result.content or "", request)

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

        # Try to find JSON object
        json_match = re.search(r'\{[^{}]*\}', json_str, re.DOTALL)
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
            self._cache_order.clear()

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
# Legacy Adapter (RFC-030 Phase 1)
# =============================================================================


class LegacyRoutingAdapter:
    """Adapter to convert UnifiedRouter decisions to legacy formats.

    Provides backward compatibility during migration from:
    - CognitiveRouter's RoutingDecision
    - TieredAttunement's AttunementResult

    Usage:
        router = UnifiedRouter(model=model)
        adapter = LegacyRoutingAdapter(router)

        # Get legacy CognitiveRouter-style decision
        legacy = await adapter.to_cognitive_router_decision("fix bug in auth.py")
    """

    def __init__(self, router: UnifiedRouter):
        self.router = router

    async def to_cognitive_router_decision(
        self,
        request: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert to CognitiveRouter RoutingDecision format.

        Returns dict matching cognitive_router.RoutingDecision.to_dict()
        """
        decision = await self.router.route(request, context)

        # Map unified intent to cognitive router intent
        intent_map = {
            Intent.CODE: "code_generation",
            Intent.EXPLAIN: "explanation",
            Intent.DEBUG: "debugging",
            Intent.CHAT: "unknown",
            Intent.SEARCH: "analysis",
            Intent.REVIEW: "code_review",
        }

        # Compute top_k and threshold from complexity
        complexity_params = {
            Complexity.TRIVIAL: {"top_k": 3, "threshold": 0.4},
            Complexity.STANDARD: {"top_k": 5, "threshold": 0.3},
            Complexity.COMPLEX: {"top_k": 8, "threshold": 0.2},
        }
        params = complexity_params.get(decision.complexity, {"top_k": 5, "threshold": 0.3})

        return {
            "intent": intent_map.get(decision.intent, "unknown"),
            "lens": decision.lens or "helper",
            "secondary_lenses": list(decision.secondary_lenses),
            "focus": list(decision.focus),
            "complexity": decision.complexity.value,
            "top_k": params["top_k"],
            "threshold": params["threshold"],
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
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
