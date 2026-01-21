"""Intent Analyzer (RFC-075).

LLM-driven intent analysis with provider context.
Analyzes user goals and determines the appropriate interaction type.
"""

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sunwell.interface.types import (
    ActionSpec,
    IntentAnalysis,
    ViewSpec,
)
from sunwell.providers.base import CalendarProvider, ListProvider, NotesProvider
from sunwell.surface.types import WorkspaceSpec

# Prompt is split into parts for readability
_PROMPT_HEADER = '''Analyze this user goal and determine the best way to help.

## User Goal
"{goal}"

## Available Context
- Lists: {available_lists}
- Upcoming events (next 7 days): {event_count}
- Recent notes: {recent_notes_count}

## Interaction Types
1. **workspace** — Full creative workspace (writing, coding, planning)
2. **view** — Display specific information (calendar, list, notes)
3. **action** — Execute immediately (add to list, create event)
4. **conversation** — Dialogue (questions, emotional support)
5. **hybrid** — Action + view together

## Action Types
- add_to_list: {{list, item}}
- complete_item: {{item_id}}
- create_event: {{title, start, duration_minutes}}
- create_reminder: {{text, when}}

## View Types
- calendar: focus {{start, end}}
- list: focus {{list_name}}
- notes: focus {{search}} or {{recent}}
- search: query

## Workspace Primitives
CodeEditor, ProseEditor, Kanban, Terminal, FileTree, Outline

## Instructions
Respond with ONLY valid JSON:

{{
  "interaction_type": "workspace|view|action|conversation|hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "action": {{"type": "...", "params": {{...}}}} or null,
  "view": {{"type": "...", "focus": {{...}}}} or null,
  "workspace": {{"primary": "...", "secondary": [], "seed_content": {{}}}} or null,
  "response": "response to user",
  "conversation_mode": "informational|empathetic|collaborative" or null
}}

Now analyze the goal:'''

_FALLBACK_RESPONSE = (
    "I'm not sure I understood. "
    "Could you tell me more about what you'd like to do?"
)


@dataclass
class IntentAnalyzer:
    """LLM-driven intent analysis with provider context."""

    model: Any  # OllamaModel or similar
    calendar: CalendarProvider | None = None
    lists: ListProvider | None = None
    notes: NotesProvider | None = None

    async def analyze(self, goal: str) -> IntentAnalysis:
        """Analyze user goal and determine appropriate interaction."""
        # Gather context about available data
        context = await self._gather_context()

        # Build prompt with context
        prompt = _PROMPT_HEADER.format(
            goal=goal,
            available_lists=", ".join(context["lists"]) or "none",
            event_count=context["event_count"],
            recent_notes_count=context["notes_count"],
        )

        # Query LLM
        from sunwell.models.protocol import GenerateOptions

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(
                temperature=0.3,  # Low temperature for consistent classification
                max_tokens=800,
            ),
        )

        # Parse response
        return self._parse_response(result.content or "")

    async def _gather_context(self) -> dict[str, Any]:
        """Gather context about available data for the prompt."""
        lists: list[str] = []
        event_count = 0
        notes_count = 0

        # Get list names
        if self.lists:
            with contextlib.suppress(Exception):
                lists = await self.lists.get_lists()

        # Count upcoming events
        if self.calendar:
            with contextlib.suppress(Exception):
                now = datetime.now()
                events = await self.calendar.get_events(now, now + timedelta(days=7))
                event_count = len(events)

        # Count recent notes
        if self.notes:
            with contextlib.suppress(Exception):
                notes = await self.notes.get_recent(limit=10)
                notes_count = len(notes)

        return {
            "lists": lists,
            "event_count": event_count,
            "notes_count": notes_count,
        }

    def _parse_response(self, response: str) -> IntentAnalysis:
        """Parse LLM JSON response into IntentAnalysis."""
        # Extract JSON from response (handle markdown code blocks)
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
            # Try to find JSON object in the response
            import re

            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._fallback_response()
            else:
                return self._fallback_response()

        return self._build_analysis(data)

    def _fallback_response(self) -> IntentAnalysis:
        """Return a fallback conversation response."""
        return IntentAnalysis(
            interaction_type="conversation",
            confidence=0.5,
            response=_FALLBACK_RESPONSE,
            reasoning="Failed to parse intent, defaulting to conversation",
        )

    def _build_analysis(self, data: dict[str, Any]) -> IntentAnalysis:
        """Build IntentAnalysis from parsed data."""
        # Build typed objects from parsed data
        action = None
        if data.get("action"):
            action = ActionSpec(
                type=data["action"]["type"],
                params=data["action"].get("params", {}),
            )

        view = None
        if data.get("view"):
            view = ViewSpec(
                type=data["view"]["type"],
                focus=data["view"].get("focus"),
                query=data["view"].get("query"),
            )

        workspace = None
        if data.get("workspace"):
            ws = data["workspace"]
            workspace = WorkspaceSpec(
                primary=ws["primary"],
                secondary=tuple(ws.get("secondary", [])),
                contextual=tuple(ws.get("contextual", [])),
                arrangement=ws.get("arrangement", "standard"),
                seed_content=ws.get("seed_content"),
            )

        return IntentAnalysis(
            interaction_type=data.get("interaction_type", "conversation"),
            confidence=data.get("confidence", 0.8),
            action=action,
            view=view,
            workspace=workspace,
            response=data.get("response"),
            reasoning=data.get("reasoning"),
            conversation_mode=data.get("conversation_mode"),
        )
