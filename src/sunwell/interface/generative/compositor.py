"""UI Compositor (RFC-082).

Fast speculative UI composition using tiered prediction strategy:
- Tier 0: Regex pre-screen (0ms)
- Tier 1: Fast model (100-200ms)
- Tier 2: Large model (2-5s, authoritative)

The compositor predicts UI layout before content is ready,
enabling instant skeleton rendering while content streams in.
"""


import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import Model

# Valid page types
PageType = str  # 'home' | 'project' | 'research' | 'planning' | 'conversation'

# Valid input modes
InputMode = str  # 'hero' | 'chat' | 'command' | 'search'


@dataclass(frozen=True, slots=True)
class PanelSpec:
    """Specification for a single auxiliary panel."""

    panel_type: str
    title: str | None = None
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "panel_type": self.panel_type,
            "title": self.title,
            "data": self.data,
        }


@dataclass(frozen=True, slots=True)
class CompositionSpec:
    """Speculative UI composition from fast analysis."""

    page_type: PageType
    panels: tuple[PanelSpec, ...]
    input_mode: InputMode
    suggested_tools: tuple[str, ...]
    confidence: float
    source: str  # 'regex' | 'fast_model' | 'large_model'

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "page_type": self.page_type,
            "panels": [p.to_dict() for p in self.panels],
            "input_mode": self.input_mode,
            "suggested_tools": list(self.suggested_tools),
            "confidence": self.confidence,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class IntentSignal:
    """Pattern-based intent signal for fast matching."""

    patterns: tuple[re.Pattern[str], ...]
    page_type: PageType
    panels: tuple[str, ...]
    input_mode: InputMode = "chat"
    tools: tuple[str, ...] = ()


@dataclass(slots=True)
class CompositionContext:
    """Context for composition prediction."""

    current_page: PageType = "home"
    recent_panels: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)


# Pre-compiled intent signals for Tier 0 regex matching
INTENT_SIGNALS: tuple[IntentSignal, ...] = (
    # Calendar/scheduling triggers
    IntentSignal(
        patterns=(
            re.compile(r"plan (my |the )?week", re.IGNORECASE),
            re.compile(r"schedule", re.IGNORECASE),
            re.compile(
                r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\d{1,2}(:\d{2})?\s*(am|pm)", re.IGNORECASE),
            re.compile(r"meeting", re.IGNORECASE),
            re.compile(r"appointment", re.IGNORECASE),
            re.compile(r"when am i free", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("calendar",),
        input_mode="chat",
    ),
    # Task/todo triggers
    IntentSignal(
        patterns=(
            re.compile(r"\btodo\b", re.IGNORECASE),
            re.compile(r"\btask", re.IGNORECASE),
            re.compile(r"remind me", re.IGNORECASE),
            re.compile(r"checklist", re.IGNORECASE),
            re.compile(r"things to do", re.IGNORECASE),
            re.compile(r"i need to", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("tasks",),
        input_mode="chat",
    ),
    # Finance triggers
    IntentSignal(
        patterns=(
            re.compile(r"budget", re.IGNORECASE),
            re.compile(r"spending", re.IGNORECASE),
            re.compile(r"\bmoney\b", re.IGNORECASE),
            re.compile(r"financ", re.IGNORECASE),
            re.compile(r"expense", re.IGNORECASE),
            re.compile(r"how much did i spend", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("chart", "upload"),
        input_mode="chat",
        tools=("upload",),
    ),
    # Code/programming triggers
    IntentSignal(
        patterns=(
            re.compile(r"\b(code|function|class|method|bug|error|exception)\b", re.IGNORECASE),
            re.compile(r"\b(python|javascript|typescript|rust|go|java|c\+\+)\b", re.IGNORECASE),
            re.compile(r"how (do|can) i (write|implement|create)", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("code",),
        input_mode="chat",
    ),
    # Location/travel triggers
    IntentSignal(
        patterns=(
            re.compile(r"where is", re.IGNORECASE),
            re.compile(r"near me", re.IGNORECASE),
            re.compile(r"directions", re.IGNORECASE),
            re.compile(r"restaurant", re.IGNORECASE),
            re.compile(r"hotel", re.IGNORECASE),
            re.compile(r"how (do|can) i get to", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("map",),
        input_mode="chat",
        tools=("location",),
    ),
    # Creative writing triggers
    IntentSignal(
        patterns=(
            re.compile(r"write (a |me )?(story|poem|essay|article)", re.IGNORECASE),
            re.compile(r"help me write", re.IGNORECASE),
            re.compile(r"\bdraft\b", re.IGNORECASE),
            re.compile(r"creative writing", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("editor",),
        input_mode="chat",
        tools=("voice",),
    ),
    # Educational/explanation triggers
    IntentSignal(
        patterns=(
            re.compile(r"how does .+ work", re.IGNORECASE),
            re.compile(r"what is .+\?", re.IGNORECASE),
            re.compile(r"explain", re.IGNORECASE),
            re.compile(r"teach me", re.IGNORECASE),
            re.compile(r"why does", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("image", "links"),
        input_mode="chat",
    ),
    # Health/fitness triggers
    IntentSignal(
        patterns=(
            re.compile(r"workout", re.IGNORECASE),
            re.compile(r"exercise", re.IGNORECASE),
            re.compile(r"calories", re.IGNORECASE),
            re.compile(r"\bsteps\b", re.IGNORECASE),
            re.compile(r"\bhealth\b", re.IGNORECASE),
            re.compile(r"\bsleep\b", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("chart",),
        input_mode="chat",
    ),
    # Shopping/product triggers
    IntentSignal(
        patterns=(
            re.compile(r"\bbuy\b", re.IGNORECASE),
            re.compile(r"\bshop", re.IGNORECASE),
            re.compile(r"product", re.IGNORECASE),
            re.compile(r"compare", re.IGNORECASE),
            re.compile(r"review", re.IGNORECASE),
            re.compile(r"recommend", re.IGNORECASE),
        ),
        page_type="conversation",
        panels=("products",),
        input_mode="chat",
    ),
    # Project triggers
    IntentSignal(
        patterns=(
            re.compile(r"open .+ project", re.IGNORECASE),
            re.compile(r"work on .+", re.IGNORECASE),
            re.compile(r"let'?s code", re.IGNORECASE),
            re.compile(r"start coding", re.IGNORECASE),
        ),
        page_type="project",
        panels=("file_tree", "code", "terminal"),
        input_mode="command",
    ),
    # Research triggers
    IntentSignal(
        patterns=(
            re.compile(r"research .+", re.IGNORECASE),
            re.compile(r"learn about", re.IGNORECASE),
            re.compile(r"\bstudy\b", re.IGNORECASE),
            re.compile(r"take notes on", re.IGNORECASE),
        ),
        page_type="research",
        panels=("notes", "sources"),
        input_mode="search",
    ),
    # Planning triggers
    IntentSignal(
        patterns=(
            re.compile(r"plan (the |my )?sprint", re.IGNORECASE),
            re.compile(r"organize (my |the )?work", re.IGNORECASE),
            re.compile(r"project board", re.IGNORECASE),
            re.compile(r"kanban", re.IGNORECASE),
        ),
        page_type="planning",
        panels=("kanban", "calendar"),
        input_mode="command",
    ),
)

# Composition schemas for validation
COMPOSITION_SCHEMAS: dict[str, dict[str, Any]] = {
    "home": {
        "valid_panels": [],
        "default_input_mode": "hero",
    },
    "conversation": {
        "valid_panels": [
            "calendar",
            "tasks",
            "chart",
            "image",
            "upload",
            "code",
            "map",
            "editor",
            "document",
            "products",
            "links",
        ],
        "max_panels": 3,
        "default_input_mode": "chat",
    },
    "project": {
        "valid_panels": [
            "file_tree",
            "terminal",
            "code",
            "preview",
            "diff",
            "test_runner",
            "deploy",
            "conversation",
        ],
        "required_panels": ["file_tree"],
        "default_input_mode": "command",
    },
    "research": {
        "valid_panels": ["notes", "sources", "web", "diagram", "citations", "conversation"],
        "required_panels": ["notes"],
        "default_input_mode": "search",
    },
    "planning": {
        "valid_panels": ["kanban", "calendar", "tasks", "timeline", "team", "progress"],
        "default_input_mode": "command",
    },
}

# Fast model prompt template
_FAST_MODEL_PROMPT = """You are a UI compositor. Given user input, predict the optimal layout.

VALID PAGE TYPES: home, project, research, planning, conversation

VALID PANELS (by page type):
- conversation: calendar, tasks, chart, image, upload, code, map, editor, document, products, links
- project: file_tree, terminal, code, preview, diff, test_runner, deploy
- research: notes, sources, web, diagram, citations
- planning: kanban, calendar, tasks, timeline, team, progress

INTENT → COMPOSITION RULES:
| Signal | Panels |
|--------|--------|
| schedule/time/day words | calendar |
| todo/task/remind | tasks |
| budget/money/spending | chart, upload |
| explain/how/what is | image, links |
| code/function/programming | code |
| where/near me/directions | map |
| write story/poem/creative | editor |
| plan week + fitness | calendar, chart |

USER INPUT: "{input}"
CURRENT PAGE: {current_page}

Respond with JSON only:
{{"page_type": "...", "panels": [{{"type": "...", "title": "..."}}], "input_mode": "...",
"tools": [...], "confidence": 0.0-1.0}}"""


@dataclass(slots=True)
class Compositor:
    """Fast UI composition prediction with tiered strategy."""

    fast_model: Model | None = None
    intent_signals: tuple[IntentSignal, ...] = INTENT_SIGNALS

    async def predict(
        self,
        user_input: str,
        context: CompositionContext | None = None,
    ) -> CompositionSpec:
        """Predict composition with tiered strategy.

        Tier 0: Regex pre-screen (0ms) - if 2+ patterns match
        Tier 1: Fast model (100-200ms) - if available
        Tier 2: Fallback to default composition
        """
        context = context or CompositionContext()

        # Tier 0: Regex pre-screen
        regex_match = self._regex_match(user_input)
        if regex_match and regex_match.confidence >= 0.9:
            return regex_match

        # Tier 1: Fast model (if available)
        if self.fast_model:
            try:
                return await self._fast_model_predict(user_input, context)
            except Exception:
                pass  # Fall through to default

        # Tier 2: Fallback - return regex match or default
        if regex_match:
            return regex_match

        return self._default_composition(context)

    def _regex_match(self, user_input: str) -> CompositionSpec | None:
        """Tier 0: Ultra-fast regex-based intent matching."""
        best_match: tuple[IntentSignal, int] | None = None

        for signal in self.intent_signals:
            hits = sum(1 for p in signal.patterns if p.search(user_input))
            if hits >= 2 and (best_match is None or hits > best_match[1]):
                best_match = (signal, hits)

        if best_match:
            signal, hits = best_match
            panels = tuple(PanelSpec(panel_type=p) for p in signal.panels)
            return CompositionSpec(
                page_type=signal.page_type,
                panels=panels,
                input_mode=signal.input_mode,
                suggested_tools=signal.tools,
                confidence=min(0.95, 0.85 + hits * 0.03),
                source="regex",
            )
        return None

    async def _fast_model_predict(
        self,
        user_input: str,
        context: CompositionContext,
    ) -> CompositionSpec:
        """Tier 1: Fast model composition prediction."""
        if not self.fast_model:
            msg = "Fast model not configured"
            raise ValueError(msg)

        prompt = _FAST_MODEL_PROMPT.format(
            input=user_input,
            current_page=context.current_page,
        )

        from sunwell.models.protocol import GenerateOptions

        result = await self.fast_model.generate(
            prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=200),
        )

        return self._parse_fast_model_response(result.content or "")

    def _parse_fast_model_response(self, response: str) -> CompositionSpec:
        """Parse fast model JSON response."""
        # Extract JSON from response
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
            return self._default_composition(CompositionContext())

        # Build panels
        panels = []
        for p in data.get("panels", []):
            if isinstance(p, dict) and p.get("type"):
                panels.append(
                    PanelSpec(
                        panel_type=p["type"],
                        title=p.get("title"),
                    )
                )

        return CompositionSpec(
            page_type=data.get("page_type", "conversation"),
            panels=tuple(panels),
            input_mode=data.get("input_mode", "chat"),
            suggested_tools=tuple(data.get("tools", [])),
            confidence=data.get("confidence", 0.7),
            source="fast_model",
        )

    def _default_composition(self, context: CompositionContext) -> CompositionSpec:
        """Fallback composition when no signals match."""
        schema = COMPOSITION_SCHEMAS.get(context.current_page, COMPOSITION_SCHEMAS["conversation"])
        return CompositionSpec(
            page_type=context.current_page,
            panels=(),
            input_mode=schema.get("default_input_mode", "chat"),
            suggested_tools=(),
            confidence=0.5,
            source="default",
        )

    def validate_composition(self, spec: CompositionSpec) -> bool:
        """Validate composition against schema."""
        schema = COMPOSITION_SCHEMAS.get(spec.page_type)
        if not schema:
            return False

        valid_panels = schema.get("valid_panels", [])
        max_panels = schema.get("max_panels", 10)

        # Check panel count
        if len(spec.panels) > max_panels:
            return False

        # Check panel types
        return all(panel.panel_type in valid_panels for panel in spec.panels)


__all__ = [
    "CompositionContext",
    "CompositionSpec",
    "Compositor",
    "IntentSignal",
    "PanelSpec",
]
