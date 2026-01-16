"""Cognitive Router - Intent-aware routing with tiny LLMs.

The CognitiveRouter is the "thinking" layer that sits between raw task
input and the retrieval system. Instead of relying solely on embedding
similarity, it performs:

1. Intent Classification — What kind of task is this?
2. Lens Selection — Which lens(es) should handle this?
3. Focus Extraction — What specific aspects matter?
4. Confidence Scoring — How certain is the routing decision?
5. Parameter Tuning — Adjust top_k, threshold based on complexity

This makes Sunwell a portable DORI — all the intelligent routing of a
Cursor-based orchestrator, but running anywhere.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from sunwell.models.protocol import ModelProtocol

if TYPE_CHECKING:
    from sunwell.core.spell import Spell, Grimoire


class Intent(str, Enum):
    """Primary intent taxonomy for task classification."""
    
    CODE_REVIEW = "code_review"
    CODE_GENERATION = "code_generation"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DEBUGGING = "debugging"
    EXPLANATION = "explanation"
    UNKNOWN = "unknown"


class Complexity(str, Enum):
    """Task complexity levels."""
    
    SIMPLE = "simple"       # Single focus, few heuristics needed
    MODERATE = "moderate"   # Multiple aspects, standard retrieval
    COMPLEX = "complex"     # Multi-faceted, needs comprehensive context


@dataclass(frozen=True, slots=True)
class IntentTaxonomy:
    """Defines the intent taxonomy for routing."""
    
    intents: tuple[Intent, ...] = tuple(Intent)
    lens_mapping: dict[Intent, str] = field(default_factory=lambda: {
        Intent.CODE_REVIEW: "code-reviewer",
        Intent.CODE_GENERATION: "helper",
        Intent.DOCUMENTATION: "tech-writer",
        Intent.ANALYSIS: "code-reviewer",
        Intent.REFACTORING: "code-reviewer",
        Intent.TESTING: "team-qa",
        Intent.DEBUGGING: "code-reviewer",
        Intent.EXPLANATION: "tech-writer",
        Intent.UNKNOWN: "helper",
    })
    
    def suggest_lens(self, intent: Intent) -> str:
        """Suggest a lens for an intent."""
        return self.lens_mapping.get(intent, "helper")


@dataclass
class RoutingDecision:
    """Output from the CognitiveRouter.
    
    Contains all information needed to configure retrieval and generation.
    """
    
    intent: Intent                      # Primary intent classification
    lens: str                           # Selected lens file (without .lens)
    secondary_lenses: list[str]         # Additional lenses to merge
    focus: list[str]                    # Key topics to boost in retrieval
    complexity: Complexity              # Task complexity
    top_k: int                          # Suggested retrieval count
    threshold: float                    # Minimum relevance threshold
    confidence: float                   # Router's confidence (0-1)
    reasoning: str                      # Brief explanation
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent.value,
            "lens": self.lens,
            "secondary_lenses": self.secondary_lenses,
            "focus": self.focus,
            "complexity": self.complexity.value,
            "top_k": self.top_k,
            "threshold": self.threshold,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingDecision:
        """Create from dictionary."""
        return cls(
            intent=Intent(data.get("intent", "unknown")),
            lens=data.get("lens", "helper"),
            secondary_lenses=data.get("secondary_lenses", []),
            focus=data.get("focus", []),
            complexity=Complexity(data.get("complexity", "moderate")),
            top_k=data.get("top_k", 5),
            threshold=data.get("threshold", 0.3),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning", ""),
        )
    
    @classmethod
    def default(cls) -> RoutingDecision:
        """Return a safe default routing decision."""
        return cls(
            intent=Intent.UNKNOWN,
            lens="helper",
            secondary_lenses=[],
            focus=[],
            complexity=Complexity.MODERATE,
            top_k=5,
            threshold=0.3,
            confidence=0.0,
            reasoning="Default routing (no classification performed)",
        )


# Complexity → retrieval parameters
COMPLEXITY_PARAMS = {
    Complexity.SIMPLE: {"top_k": 3, "threshold": 0.4},
    Complexity.MODERATE: {"top_k": 5, "threshold": 0.3},
    Complexity.COMPLEX: {"top_k": 8, "threshold": 0.2},
}

# DORI-compatible command mappings (module-level constant)
DORI_COMMAND_MAP: dict[str, dict[str, Any]] = {
    # Audit & Validation
    "::a": {"intent": "code_review", "lens": "code-reviewer", "focus": ["audit", "validation", "accuracy"]},
    "::audit": {"intent": "code_review", "lens": "code-reviewer", "focus": ["audit", "validation", "accuracy"]},
    "::health": {"intent": "analysis", "lens": "code-reviewer", "focus": ["health", "drift", "quality"]},
    
    # Content Operations
    "::w": {"intent": "documentation", "lens": "tech-writer", "focus": ["writing", "clarity", "structure"]},
    "::write": {"intent": "documentation", "lens": "tech-writer", "focus": ["writing", "clarity", "structure"]},
    "::pipeline": {"intent": "documentation", "lens": "tech-writer", "focus": ["research", "draft", "verify"], "workflow": "pipeline"},
    "::p": {"intent": "documentation", "lens": "tech-writer", "focus": ["polish", "style", "clarity"]},
    "::polish": {"intent": "documentation", "lens": "tech-writer", "focus": ["polish", "style", "clarity"]},
    
    # Code Operations
    "::review": {"intent": "code_review", "lens": "code-reviewer", "focus": ["review", "quality", "issues"]},
    "::test": {"intent": "testing", "lens": "team-qa", "focus": ["testing", "coverage", "edge cases"]},
    "::refactor": {"intent": "refactoring", "lens": "code-reviewer", "focus": ["refactoring", "clean code", "patterns"]},
    
    # Architecture
    "::arch": {"intent": "explanation", "lens": "tech-writer", "focus": ["architecture", "design", "components"]},
    "::overview": {"intent": "explanation", "lens": "tech-writer", "focus": ["overview", "introduction", "purpose"]},
}


@dataclass
class CognitiveRouter:
    """Intent-aware routing using a tiny LLM.
    
    The router is the "thinking" layer that decides:
    - What kind of task is this?
    - Which lens should handle it?
    - What to focus on during retrieval?
    - How many heuristics to retrieve?
    
    This replaces DORI's rule-based routing with a learned,
    adaptive approach that works anywhere.
    
    RFC-021 Extension:
    The router now integrates with the Grimoire (spell manager) to provide
    fast-path routing for spell incantations (::security, ::audit, etc.).
    
    Example:
        router = CognitiveRouter(
            router_model=OllamaModel("functiongemma:latest"),
            available_lenses=["code-reviewer", "tech-writer", "team-qa"],
        )
        
        decision = await router.route("Review this code for security issues")
        # decision.intent = Intent.CODE_REVIEW
        # decision.lens = "code-reviewer"
        # decision.focus = ["security", "injection", "authentication"]
        # decision.confidence = 0.92
        
        # With spell:
        decision, spell = await router.route_with_spell("::security auth.py")
        # spell contains full execution context
    """
    
    router_model: ModelProtocol
    available_lenses: list[str]
    taxonomy: IntentTaxonomy = field(default_factory=IntentTaxonomy)
    grimoire: "Grimoire | None" = None  # RFC-021: Spell manager
    
    # Routing history for learning
    _history: list[tuple[str, RoutingDecision]] = field(default_factory=list)
    
    async def route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Route a task to the appropriate lens and retrieval parameters.
        
        Supports DORI-compatible commands (::a, ::pipeline, etc.) as well as
        natural language task descriptions.
        
        Args:
            task: The task description or command to route
            context: Optional context (file content, metadata, etc.)
            
        Returns:
            RoutingDecision with all routing information
        """
        # RFC-021: Check for spell incantations first (Grimoire takes priority)
        if self.grimoire:
            spell = self._check_spell(task)
            if spell:
                decision = spell.to_routing_decision()
                self._history.append((task, decision))
                return decision
        
        # Check for DORI-style commands (fast path, legacy support)
        command_decision = self._check_command(task)
        if command_decision:
            self._history.append((task, command_decision))
            return command_decision
        
        # Natural language routing via LLM
        prompt = self._build_routing_prompt(task, context)
        
        try:
            response = await self.router_model.generate(prompt)
            decision = self._parse_response(response.content)
            
            # Record for learning
            self._history.append((task, decision))
            
            return decision
            
        except Exception as e:
            # Fallback to heuristic routing on LLM failure
            return self._heuristic_fallback(task, error=str(e))

    async def route_with_spell(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[RoutingDecision, "Spell | None"]:
        """Route a task, returning both routing decision and spell context.
        
        This is the RFC-021 enhanced routing method that returns full spell
        context (instructions, templates, quality gates) alongside routing.
        
        Args:
            task: The task description or spell incantation
            context: Optional context (file content, metadata, etc.)
            
        Returns:
            Tuple of (RoutingDecision, Spell or None)
        """
        # Check for spell incantations first
        if self.grimoire:
            spell = self._check_spell(task)
            if spell:
                decision = spell.to_routing_decision()
                self._history.append((task, decision))
                return decision, spell
        
        # Standard routing (no spell context)
        decision = await self.route(task, context)
        return decision, None

    def _check_spell(self, task: str) -> "Spell | None":
        """Check if task matches a spell incantation.
        
        Extracts the incantation from the task and resolves it via Grimoire.
        """
        if not self.grimoire:
            return None
        
        task_stripped = task.strip()
        
        if not task_stripped.startswith("::"):
            return None
        
        # Extract incantation (first word)
        parts = task_stripped.split(maxsplit=1)
        incantation = parts[0].lower()
        
        return self.grimoire.resolve(incantation)
    
    def _check_command(self, task: str) -> RoutingDecision | None:
        """Check if task is a DORI-style command and return fast-path routing."""
        task_stripped = task.strip()
        
        # Extract command (first word if starts with ::)
        if not task_stripped.startswith("::"):
            return None
        
        parts = task_stripped.split(maxsplit=1)
        command = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        
        if command not in DORI_COMMAND_MAP:
            return None
        
        mapping = DORI_COMMAND_MAP[command]
        
        # Validate lens exists
        lens = mapping["lens"]
        if lens not in self.available_lenses:
            lens = self.available_lenses[0] if self.available_lenses else "helper"
        
        return RoutingDecision(
            intent=Intent(mapping["intent"]),
            lens=lens,
            secondary_lenses=[],
            focus=mapping["focus"],
            complexity=Complexity.MODERATE,
            top_k=5,
            threshold=0.3,
            confidence=1.0,  # Commands are deterministic
            reasoning=f"DORI command: {command}" + (f" (workflow: {mapping.get('workflow')})" if mapping.get('workflow') else ""),
        )
    
    def _build_routing_prompt(
        self,
        task: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Build a structured prompt for the router model."""
        
        lenses_str = "\n".join(f"- {lens}" for lens in self.available_lenses)
        intents_str = "\n".join(f"- {i.value}: {i.name.replace('_', ' ').title()}" 
                                for i in Intent if i != Intent.UNKNOWN)
        
        context_str = ""
        if context:
            if "file_path" in context:
                context_str += f"File: {context['file_path']}\n"
            if "language" in context:
                context_str += f"Language: {context['language']}\n"
            if "code_snippet" in context:
                snippet = context["code_snippet"][:500]  # Truncate
                context_str += f"Code:\n```\n{snippet}\n```\n"
        
        return f"""You are a task router. Analyze the task and decide how to handle it.

AVAILABLE LENSES:
{lenses_str}

INTENT TAXONOMY:
{intents_str}

TASK:
{task}

{f'CONTEXT:\n{context_str}' if context_str else ''}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "intent": "<intent from taxonomy>",
  "lens": "<lens name from list>",
  "secondary_lenses": ["<optional additional lens>"],
  "focus": ["<keyword1>", "<keyword2>", "<keyword3>"],
  "complexity": "simple|moderate|complex",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence explanation>"
}}"""
    
    def _parse_response(self, response: str) -> RoutingDecision:
        """Parse the router model's response into a RoutingDecision."""
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if not json_match:
            # Try to find JSON in code blocks
            code_match = re.search(r'```(?:json)?\s*(\{[^`]*\})\s*```', response, re.DOTALL)
            if code_match:
                json_str = code_match.group(1)
            else:
                raise ValueError(f"No JSON found in response: {response[:200]}")
        else:
            json_str = json_match.group(0)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        # Parse intent
        intent_str = data.get("intent", "unknown").lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            intent = Intent.UNKNOWN
        
        # Parse complexity
        complexity_str = data.get("complexity", "moderate").lower()
        try:
            complexity = Complexity(complexity_str)
        except ValueError:
            complexity = Complexity.MODERATE
        
        # Get retrieval params based on complexity
        params = COMPLEXITY_PARAMS[complexity]
        
        # Parse lens (validate against available)
        lens = data.get("lens", "helper")
        if lens not in self.available_lenses:
            # Try to match partial
            for available in self.available_lenses:
                if lens.lower() in available.lower():
                    lens = available
                    break
            else:
                lens = self.taxonomy.suggest_lens(intent)
        
        return RoutingDecision(
            intent=intent,
            lens=lens,
            secondary_lenses=data.get("secondary_lenses", []),
            focus=data.get("focus", []),
            complexity=complexity,
            top_k=data.get("top_k", params["top_k"]),
            threshold=data.get("threshold", params["threshold"]),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
        )
    
    def _heuristic_fallback(
        self,
        task: str,
        error: str | None = None,
    ) -> RoutingDecision:
        """Fallback to keyword-based routing when LLM fails.
        
        This ensures the system degrades gracefully.
        """
        task_lower = task.lower()
        
        # Keyword-based intent detection
        intent = Intent.UNKNOWN
        lens = "helper"
        focus: list[str] = []
        
        # Security / code review patterns
        if any(kw in task_lower for kw in ["security", "vulnerability", "injection", "xss", "csrf"]):
            intent = Intent.CODE_REVIEW
            lens = "code-reviewer"
            focus = ["security", "vulnerability", "validation"]
        
        # Performance patterns
        elif any(kw in task_lower for kw in ["performance", "optimize", "slow", "fast", "speed"]):
            intent = Intent.REFACTORING
            lens = "code-reviewer"
            focus = ["performance", "optimization", "efficiency"]
        
        # Testing patterns
        elif any(kw in task_lower for kw in ["test", "unittest", "pytest", "coverage"]):
            intent = Intent.TESTING
            lens = "team-qa"
            focus = ["testing", "edge cases", "assertions"]
        
        # Documentation patterns
        elif any(kw in task_lower for kw in ["document", "docstring", "readme", "explain"]):
            intent = Intent.DOCUMENTATION
            lens = "tech-writer"
            focus = ["clarity", "examples", "structure"]
        
        # Review patterns
        elif any(kw in task_lower for kw in ["review", "check", "audit", "analyze"]):
            intent = Intent.CODE_REVIEW
            lens = "code-reviewer"
            focus = ["quality", "patterns", "issues"]
        
        # Generation patterns
        elif any(kw in task_lower for kw in ["write", "create", "implement", "add", "build"]):
            intent = Intent.CODE_GENERATION
            lens = "helper"
            focus = ["implementation", "patterns", "best practices"]
        
        # Validate lens is available
        if lens not in self.available_lenses:
            lens = self.available_lenses[0] if self.available_lenses else "helper"
        
        reasoning = "Heuristic fallback"
        if error:
            reasoning += f" (LLM error: {error[:50]})"
        
        return RoutingDecision(
            intent=intent,
            lens=lens,
            secondary_lenses=[],
            focus=focus,
            complexity=Complexity.MODERATE,
            top_k=5,
            threshold=0.3,
            confidence=0.3,  # Lower confidence for heuristic
            reasoning=reasoning,
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get router statistics."""
        if not self._history:
            return {
                "total_routes": 0,
                "avg_confidence": 0.0,
                "intent_distribution": {},
                "lens_distribution": {},
            }
        
        confidences = [d.confidence for _, d in self._history]
        intents = [d.intent.value for _, d in self._history]
        lenses = [d.lens for _, d in self._history]
        
        intent_counts: dict[str, int] = {}
        for i in intents:
            intent_counts[i] = intent_counts.get(i, 0) + 1
        
        lens_counts: dict[str, int] = {}
        for l in lenses:
            lens_counts[l] = lens_counts.get(l, 0) + 1
        
        return {
            "total_routes": len(self._history),
            "avg_confidence": sum(confidences) / len(confidences),
            "intent_distribution": intent_counts,
            "lens_distribution": lens_counts,
        }


class HybridRouter:
    """Combines rule-based fast paths with LLM routing.
    
    For maximum performance:
    1. Check rules first (instant, no LLM call)
    2. Fall back to LLM for novel cases
    
    This is the best of both worlds: DORI's speed for common
    patterns, LLM's flexibility for everything else.
    """
    
    @dataclass
    class Rule:
        """A fast-path routing rule."""
        pattern: re.Pattern[str]
        decision: RoutingDecision
        
        def matches(self, task: str) -> bool:
            return bool(self.pattern.search(task.lower()))
    
    def __init__(
        self,
        llm_router: CognitiveRouter,
        rules: list[Rule] | None = None,
    ):
        self.llm = llm_router
        self.rules = rules or []
        
        # Track fast-path vs LLM usage
        self._fast_path_hits = 0
        self._llm_calls = 0
    
    def add_rule(
        self,
        pattern: str,
        intent: Intent,
        lens: str,
        focus: list[str],
    ) -> None:
        """Add a fast-path rule."""
        self.rules.append(self.Rule(
            pattern=re.compile(pattern, re.IGNORECASE),
            decision=RoutingDecision(
                intent=intent,
                lens=lens,
                secondary_lenses=[],
                focus=focus,
                complexity=Complexity.MODERATE,
                top_k=5,
                threshold=0.3,
                confidence=0.95,  # High confidence for rules
                reasoning=f"Rule match: {pattern}",
            ),
        ))
    
    async def route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Route using rules first, LLM as fallback."""
        
        # Fast path: check rules
        for rule in self.rules:
            if rule.matches(task):
                self._fast_path_hits += 1
                return rule.decision
        
        # Slow path: LLM routing
        self._llm_calls += 1
        return await self.llm.route(task, context)
    
    def compile_from_history(
        self,
        min_occurrences: int = 5,
        min_quality: float = 8.0,
    ) -> list[Rule]:
        """Compile successful routing patterns into rules.
        
        Analyzes LLM routing history and creates fast-path rules
        for patterns that consistently route the same way with
        high quality outcomes.
        
        Returns newly created rules.
        """
        # This would analyze self.llm._history and feedback data
        # to create optimized rules. Placeholder for now.
        return []
    
    def get_stats(self) -> dict[str, Any]:
        """Get hybrid router statistics."""
        total = self._fast_path_hits + self._llm_calls
        return {
            "total_routes": total,
            "fast_path_hits": self._fast_path_hits,
            "fast_path_rate": self._fast_path_hits / total if total > 0 else 0,
            "llm_calls": self._llm_calls,
            "rules_count": len(self.rules),
            "llm_stats": self.llm.get_stats(),
        }
