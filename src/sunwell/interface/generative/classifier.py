"""Intent Classifier — Step 1 of Two-Step Pipeline.

Classifies user intent into structured routing decisions.
Does NOT generate user-facing responses — that's the ResponseGenerator's job.

This separation ensures:
1. Routing decisions are deterministic and testable
2. Response text cannot contradict routing (it's generated knowing the route)
3. Classifier can use a tiny model (fast, cheap)

See: RFC-075 (original), this refactor improves on it.
"""


import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

from sunwell.interface.generative.types import ActionSpec, InteractionType, ViewSpec
from sunwell.interface.generative.surface.types import WorkspaceSpec

# =============================================================================
# PRE-COMPILED PATTERNS — Avoid re-compilation per call
# =============================================================================

_JSON_EXTRACT_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

# =============================================================================
# CLASSIFICATION PROMPT — Structured output only, no response generation
# =============================================================================

_CLASSIFIER_PROMPT = '''Classify this user intent. Return ONLY a JSON routing decision.

## User Goal
"{goal}"

## Available Context
{context}

## Conversation History
{history}

## Route Types
- **workspace**: User wants to CREATE something complex (app, game, site, document, plan)
- **view**: User wants to SEE specific information (calendar, files, notes, projects)
- **action**: User wants to DO something immediately (add item, create event, complete task)
- **conversation**: User wants to DISCUSS/ASK (questions, explanations, emotional support)
- **hybrid**: Action + view together (add item then show list)

## CRITICAL ROUTING RULES

WORKSPACE triggers (use workspace, NOT conversation):
- "build", "create", "make", "develop", "implement" + app/game/site/tool/project/system
- "write code for", "code a", "program a"
- "start a new project", "new app", "new game"
- "plan", "design", "architect" + something complex
- User wants to CREATE something that requires multiple files/steps → workspace

CONVERSATION triggers:
- Vague requests without clear deliverable ("help me with something")
- Emotional/social: greetings, feelings, opinions, encouragement
- Questions about concepts: "what is", "how does X work", "explain"
- Clarifying questions when intent is unclear

ACTION triggers:
- Imperative + simple task: "add X to list", "remind me", "set timer"
- Single-step operations that complete immediately

VIEW triggers:
- "show me", "display", "list", "what's on my" + calendar/list/etc.
- Looking up existing information

## Workspace Primitives
CodeEditor, ProseEditor, KanbanBoard, Terminal, FileTree, Outline,
DataTable, Preview, DiffView, Timeline, GoalTree

## Output Format
Return ONLY valid JSON (no markdown, no explanation):

{{
  "route": "workspace|view|action|conversation|hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of classification",
  "workspace": {{"primary": "...", "secondary": [...], "arrangement": "..."}} or null,
  "view": {{"type": "calendar|list|files|projects|...", "focus": {{...}}}} or null,
  "action": {{"type": "add_to_list|create_event|...", "params": {{...}}}} or null,
  "conversation_mode": "informational|empathetic|collaborative" or null,
  "auxiliary_panels": [{{"panel_type": "...", "data": {{...}}}}] or [],
  "suggested_tools": ["upload", "camera", ...] or []
}}'''


# =============================================================================
# HEURISTIC PATTERNS — Pre-compiled for fast path
# =============================================================================

_WORKSPACE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(build|create|make|develop|implement|write)\s+(a|an|the|me|us)?\s*\w*\s*"
        r"(app|application|game|site|website|webapp|tool|project|system|platform|service|api|backend|frontend|cli|script)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(start|begin|new)\s+(a|an)?\s*(project|app|game|codebase)", re.IGNORECASE),
    re.compile(r"\b(code|program|develop)\s+(a|an|the|me)?\s*\w+", re.IGNORECASE),
    re.compile(r"\blet'?s?\s+(build|create|make|code|develop)", re.IGNORECASE),
    re.compile(r"\bi\s+want\s+to\s+(build|create|make|code|develop)", re.IGNORECASE),
)

_ACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(add|put)\s+.+\s+(to|on|in)\s+(my\s+)?(list|todo|calendar|reminders?)", re.IGNORECASE
    ),
    re.compile(r"\b(remind|alert)\s+me\s+(to|about|at|in)", re.IGNORECASE),
    re.compile(r"\b(set|create)\s+(a\s+)?(timer|alarm|reminder)", re.IGNORECASE),
    re.compile(r"\b(complete|finish|done|check\s+off)\s+.+", re.IGNORECASE),
)

_VIEW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(show|display|list|what'?s?\s+(on|in))\s+(my\s+)?"
        r"(calendar|schedule|events?|tasks?|todos?|list|files?|projects?)",
        re.IGNORECASE,
    ),
    re.compile(r"\bmy\s+(calendar|schedule|events?|tasks?|todos?)", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Structured routing decision from classifier."""

    route: InteractionType
    confidence: float
    reasoning: str
    workspace: WorkspaceSpec | None = None
    view: ViewSpec | None = None
    action: ActionSpec | None = None
    conversation_mode: str | None = None
    auxiliary_panels: tuple[dict[str, Any], ...] = ()
    suggested_tools: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        import dataclasses

        workspace_dict = None
        if self.workspace:
            workspace_dict = {
                "primary": self.workspace.primary,
                "secondary": list(self.workspace.secondary),
                "contextual": list(self.workspace.contextual),
                "arrangement": self.workspace.arrangement,
                "seed_content": self.workspace.seed_content,
            }

        view_dict = None
        if self.view:
            if dataclasses.is_dataclass(self.view):
                view_dict = dataclasses.asdict(self.view)
            else:
                view_dict = {
                    "type": self.view.type,
                    "focus": self.view.focus,
                }

        action_dict = None
        if self.action:
            if dataclasses.is_dataclass(self.action):
                action_dict = dataclasses.asdict(self.action)
            else:
                action_dict = {
                    "type": self.action.type,
                    "params": self.action.params,
                }

        return {
            "route": self.route,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "workspace": workspace_dict,
            "view": view_dict,
            "action": action_dict,
            "conversation_mode": self.conversation_mode,
            "auxiliary_panels": list(self.auxiliary_panels),
            "suggested_tools": list(self.suggested_tools),
        }


@dataclass(slots=True)
class IntentClassifier:
    """Classifies user intent into structured routing decisions.

    Uses a two-tier approach:
    1. Fast heuristics for high-confidence patterns
    2. LLM for ambiguous cases

    Example:
        >>> classifier = IntentClassifier(model=tiny_model)
        >>> result = await classifier.classify("build a chat app")
        >>> result.route
        'workspace'
        >>> result.workspace.primary
        'CodeEditor'
    """

    model: ModelProtocol
    """Model for classification (can be tiny, e.g., 1B params)."""

    use_heuristics: bool = True
    """Whether to try fast heuristics before LLM."""

    heuristic_confidence: float = 0.85
    """Confidence level for heuristic matches."""

    _cache: dict[str, ClassificationResult] = field(default_factory=dict)
    """LRU cache for repeated queries."""

    async def classify(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> ClassificationResult:
        """Classify user intent into a routing decision.

        Args:
            goal: User's stated goal
            context: Available data context (lists, events, etc.)
            history: Conversation history for multi-turn context

        Returns:
            ClassificationResult with route type and specs
        """
        # Check cache first
        cache_key = f"{goal}:{hash(str(context))}:{hash(str(history))}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try fast heuristics first
        if self.use_heuristics:
            heuristic_result = self._heuristic_classify(goal)
            if heuristic_result:
                self._cache[cache_key] = heuristic_result
                return heuristic_result

        # Fall back to LLM classification
        result = await self._llm_classify(goal, context, history)
        self._cache[cache_key] = result
        return result

    def _heuristic_classify(self, goal: str) -> ClassificationResult | None:
        """Fast pattern-based classification for high-confidence cases."""
        goal_lower = goal.lower().strip()

        # Check workspace patterns (pre-compiled, case-insensitive)
        for pattern in _WORKSPACE_PATTERNS:
            if pattern.search(goal_lower):
                return ClassificationResult(
                    route="workspace",
                    confidence=self.heuristic_confidence,
                    reasoning=f"Matched workspace pattern: {pattern.pattern[:30]}...",
                    workspace=WorkspaceSpec(
                        primary="CodeEditor",
                        secondary=("FileTree",),
                        contextual=(),
                        arrangement="standard",
                    ),
                )

        # Check action patterns (pre-compiled)
        for pattern in _ACTION_PATTERNS:
            if pattern.search(goal_lower):
                return ClassificationResult(
                    route="action",
                    confidence=self.heuristic_confidence,
                    reasoning=f"Matched action pattern: {pattern.pattern[:30]}...",
                )

        # Check view patterns (pre-compiled)
        for pattern in _VIEW_PATTERNS:
            if pattern.search(goal_lower):
                return ClassificationResult(
                    route="view",
                    confidence=self.heuristic_confidence,
                    reasoning=f"Matched view pattern: {pattern.pattern[:30]}...",
                )

        # No high-confidence match — need LLM
        return None

    async def _llm_classify(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> ClassificationResult:
        """LLM-based classification for ambiguous cases."""
        # Format context
        context_str = self._format_context(context) if context else "No context available"

        # Format history
        history_str = "None"
        if history:
            history_lines = []
            for msg in history[-4:]:  # Last 4 messages
                role = msg.get("role", "user").title()
                content = msg.get("content", "")[:200]
                history_lines.append(f"{role}: {content}")
            history_str = "\n".join(history_lines)

        # Build prompt
        prompt = _CLASSIFIER_PROMPT.format(
            goal=goal,
            context=context_str,
            history=history_str,
        )

        # Query LLM with low temperature for consistency
        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.1,  # Very low for deterministic classification
                max_tokens=500,
            ),
        )

        # Parse response
        return self._parse_response(result.content or "", goal)

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dict into prompt string."""
        lines = []
        if context.get("lists"):
            lines.append(f"- Lists: {', '.join(context['lists'])}")
        if context.get("event_count"):
            lines.append(f"- Upcoming events: {context['event_count']}")
        if context.get("notes_count"):
            lines.append(f"- Recent notes: {context['notes_count']}")
        if context.get("projects_available"):
            lines.append("- Projects: available")
        if context.get("habits_count"):
            lines.append(f"- Habits tracked: {context['habits_count']}")
        return "\n".join(lines) if lines else "No context available"

    def _parse_response(self, response: str, goal: str) -> ClassificationResult:
        """Parse LLM JSON response into ClassificationResult."""
        # Extract JSON
        json_str = response.strip()

        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            parts = response.split("```")
            if len(parts) >= 2:
                json_str = parts[1]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # Try to find JSON object (pre-compiled pattern)
            match = _JSON_EXTRACT_PATTERN.search(response)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._fallback_result(goal)
            else:
                return self._fallback_result(goal)

        return self._build_result(data)

    def _build_result(self, data: dict[str, Any]) -> ClassificationResult:
        """Build ClassificationResult from parsed JSON."""
        route = data.get("route", "conversation")
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning", "LLM classification")

        # Parse workspace spec
        workspace = None
        if data.get("workspace"):
            ws = data["workspace"]
            workspace = WorkspaceSpec(
                primary=ws.get("primary", "CodeEditor"),
                secondary=tuple(ws.get("secondary", [])),
                contextual=tuple(ws.get("contextual", [])),
                arrangement=ws.get("arrangement", "standard"),
                seed_content=ws.get("seed_content"),
            )

        # Parse view spec
        view = None
        if data.get("view"):
            v = data["view"]
            view = ViewSpec(type=v.get("type", "generic"), focus=v.get("focus", {}))

        # Parse action spec
        action = None
        if data.get("action"):
            a = data["action"]
            action = ActionSpec(type=a.get("type", "unknown"), params=a.get("params", {}))

        return ClassificationResult(
            route=route,
            confidence=confidence,
            reasoning=reasoning,
            workspace=workspace,
            view=view,
            action=action,
            conversation_mode=data.get("conversation_mode"),
            auxiliary_panels=tuple(data.get("auxiliary_panels", [])),
            suggested_tools=tuple(data.get("suggested_tools", [])),
        )

    def _fallback_result(self, goal: str) -> ClassificationResult:
        """Return fallback when parsing fails."""
        # Try heuristics one more time as fallback
        heuristic = self._heuristic_classify(goal)
        if heuristic:
            return heuristic

        return ClassificationResult(
            route="conversation",
            confidence=0.3,
            reasoning="Failed to parse LLM response, falling back to conversation",
            conversation_mode="informational",
        )

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        self._cache.clear()
