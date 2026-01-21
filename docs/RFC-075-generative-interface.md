# RFC-075: Generative Interface — LLM-Driven Interaction Routing

**Status**: Draft  
**Created**: 2026-01-21  
**Last Updated**: 2026-01-21  
**Authors**: Sunwell Team  
**Confidence**: 85% 🟢  
**Depends on**:
- RFC-043 (Sunwell Studio) — GUI framework
- RFC-061 (Holy Light Design System) — Visual styling
- RFC-065 (Unified Memory) — Context and learnings
- RFC-072 (Surface Primitives) — Workspace rendering (renamed from "Generative Surface")
- Local LLM — Intent analysis (3B+ parameter model)

---

## Summary

Implement a **Generative Interface** — an LLM-driven system that analyzes user goals and manifests the appropriate interaction type. Instead of a fixed UI with modes, the interface adapts to what the user actually needs: a full workspace, a simple view, an executed action, or just conversation.

**The insight**: The question isn't "which workspace layout?" — it's "what kind of interaction does this moment need?" A pirate novel needs a writing workspace. A grocery list item needs an action. A question about the weekend needs a calendar view. Emotional support needs empathetic conversation.

**Core capability**: Given any natural language input, determine:
1. What **interaction type** is appropriate (workspace, view, action, conversation)
2. What **data** is relevant (calendar, lists, notes, memory)
3. What **interface** should manifest
4. What **response** to give the user

---

## Goals

1. **Intent understanding** — LLM analyzes goals semantically, not via keyword matching
2. **Interaction routing** — Route to workspace, view, action, or conversation as appropriate
3. **Provider abstraction** — Clean interfaces for data sources (Sunwell-native now, external later)
4. **Action execution** — Execute simple actions (add to list, create event) immediately
5. **Graceful conversation** — Handle non-task input (questions, emotional support) appropriately
6. **Memory integration** — Use RFC-065 memory for context and personalization

## Non-Goals

1. **External integrations in v1** — Google Calendar, Todoist, etc. come later via provider interfaces
2. **Voice interface** — Text input only for now
3. **Multi-turn planning** — Single-turn intent analysis; complex planning uses workspace mode
4. **Autonomous actions** — All actions require user initiation (no proactive "you should...")

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Intent analysis** | Local LLM (3B+) | Semantic understanding required; keywords too brittle |
| **Model size** | 3-7B (Phi-3, Llama-3.2) | Balances capability with local performance |
| **Data storage** | Sunwell-native (local JSON/markdown) | No external dependencies; clean provider interfaces for future |
| **Action execution** | Immediate with confirmation | Fast feedback; toast notifications for actions |
| **Workspace rendering** | Delegate to RFC-072 | Separation of concerns; RFC-072 handles primitives |
| **Fallback** | Conversation mode | If intent unclear, default to helpful chat |

---

## Motivation

### The Limitation of Workspace Composition

RFC-072 (Surface Primitives) answers: "Given a workspace is needed, how should it be arranged?"

But it can't answer:
- Should this even BE a workspace?
- Is this a quick action that needs no UI?
- Is this a question that needs an answer, not a surface?
- Is this emotional support that needs empathy, not tools?

### The Spectrum of Interactions

Real user input spans a wide spectrum:

```
"write a pirate novel with 4 chapters"
    → Full workspace (ProseEditor + Outline + WordCount)
    → This is a PROJECT

"build a forum app"
    → Full workspace (CodeEditor + FileTree + Terminal)
    → This is a PROJECT

"what am i doing this weekend?"
    → Calendar view + natural language answer
    → This is a QUESTION

"add broccoli to my grocery list"
    → Execute action + toast confirmation
    → This is an ACTION

"remind me to call mom tomorrow"
    → Create reminder + confirmation
    → This is an ACTION

"i think my dad hates me what do i do?"
    → Empathetic conversation, no tools
    → This is EMOTIONAL SUPPORT

"what's the capital of France?"
    → Just answer: "Paris"
    → This is a QUESTION
```

**Keyword matching can't distinguish these.** You need semantic understanding.

### Why This Matters for Sunwell

Sunwell's vision is a **universal creative platform**. That means handling ANY creative or productive intent — not just code, not just writing, but the full range of human goals.

The interface itself must be generative: manifesting whatever interaction serves the user's actual need.

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       GENERATIVE INTERFACE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         USER INPUT                                  │ │
│  │              "add broccoli to my grocery list"                      │ │
│  └───────────────────────────────┬────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      INTENT ANALYZER                                │ │
│  │                      (Local LLM: 3-7B)                              │ │
│  │                                                                     │ │
│  │   Input: goal + available data context                              │ │
│  │   Output: IntentAnalysis {                                          │ │
│  │     interaction_type: "action",                                     │ │
│  │     action: { type: "add_to_list", list: "grocery", item: "..." }, │ │
│  │     response: "Added broccoli to your grocery list."               │ │
│  │   }                                                                 │ │
│  └───────────────────────────────┬────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    INTERACTION ROUTER                               │ │
│  │                                                                     │ │
│  │   workspace   → RFC-072 Surface Composer                            │ │
│  │   view        → View Renderer (calendar, list, search, notes)       │ │
│  │   action      → Action Executor + Confirmation Toast                │ │
│  │   conversation→ Chat Interface                                      │ │
│  │   hybrid      → Action + View combination                           │ │
│  └───────────────────────────────┬────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      DATA PROVIDERS                                 │ │
│  │                   (Pluggable Interfaces)                            │ │
│  │                                                                     │ │
│  │   CalendarProvider ──── SunwellCalendar (v1)                       │ │
│  │                     └── GoogleCalendar (future)                     │ │
│  │                                                                     │ │
│  │   ListProvider ──────── SunwellLists (v1)                          │ │
│  │                     └── Todoist (future)                            │ │
│  │                                                                     │ │
│  │   NotesProvider ─────── SunwellNotes (v1)                          │ │
│  │                     └── Obsidian (future)                           │ │
│  │                                                                     │ │
│  │   MemoryProvider ────── RFC-065 MemoryStore                        │ │
│  │                                                                     │ │
│  │   ProjectProvider ───── Existing Sunwell projects                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    RENDERED INTERFACE                               │ │
│  │                                                                     │ │
│  │   Could be:                                                         │ │
│  │   • Full workspace (ProseEditor + Outline)         [workspace]     │ │
│  │   • Calendar view focused on weekend               [view]          │ │
│  │   • Toast: "✓ Added broccoli to grocery list"     [action]        │ │
│  │   • Chat bubble with empathetic response           [conversation] │ │
│  │   • Calendar view + "You have dinner Saturday"     [hybrid]       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Interaction Types

```python
# src/sunwell/interface/types.py

from dataclasses import dataclass
from typing import Literal, Any


InteractionType = Literal["workspace", "view", "action", "conversation", "hybrid"]


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """Specification for an executable action."""
    
    type: str
    """Action type: "add_to_list", "create_event", "create_reminder", etc."""
    
    params: dict[str, Any]
    """Action parameters: {"list": "grocery", "item": "broccoli"}"""


@dataclass(frozen=True, slots=True)
class ViewSpec:
    """Specification for a view to display."""
    
    type: str
    """View type: "calendar", "list", "notes", "search"."""
    
    focus: dict[str, Any] | None = None
    """Focus parameters: {"date_range": "2026-01-25..2026-01-26"}"""
    
    query: str | None = None
    """Search query if applicable."""


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    """Specification for a workspace layout (passed to RFC-072)."""
    
    primary: str
    """Primary primitive: "CodeEditor", "ProseEditor", "Kanban", etc."""
    
    secondary: tuple[str, ...] = ()
    """Secondary primitives: ("FileTree", "Terminal")"""
    
    contextual: tuple[str, ...] = ()
    """Contextual widgets: ("WordCount", "MemoryPane")"""
    
    arrangement: str = "standard"
    """Layout arrangement: "standard", "focused", "split", "dashboard"."""
    
    seed_content: dict[str, Any] | None = None
    """Pre-populated content: {"outline": ["Chapter 1", "Chapter 2"]}"""


@dataclass(frozen=True, slots=True)
class IntentAnalysis:
    """LLM's analysis of user intent."""
    
    interaction_type: InteractionType
    """What kind of interaction this needs."""
    
    confidence: float
    """Model's confidence in this analysis (0.0-1.0)."""
    
    action: ActionSpec | None = None
    """For action/hybrid: what to execute."""
    
    view: ViewSpec | None = None
    """For view/hybrid: what to display."""
    
    workspace: WorkspaceSpec | None = None
    """For workspace: layout specification."""
    
    response: str | None = None
    """Natural language response to user."""
    
    reasoning: str | None = None
    """Why this interaction type was chosen (for debugging/transparency)."""
    
    conversation_mode: str | None = None
    """For conversation: "informational", "empathetic", "collaborative"."""
```

### Intent Analyzer

```python
# src/sunwell/interface/analyzer.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json

from sunwell.interface.types import (
    IntentAnalysis,
    InteractionType,
    ActionSpec,
    ViewSpec,
    WorkspaceSpec,
)
from sunwell.providers.base import CalendarProvider, ListProvider, NotesProvider
from sunwell.memory.store import MemoryStore
from sunwell.llm.local import LocalLLM


INTENT_ANALYSIS_PROMPT = '''Analyze this user goal and determine the best way to help.

## User Goal
"{goal}"

## Available Context
- Lists: {available_lists}
- Upcoming events (next 7 days): {event_count}
- Recent notes: {recent_notes_count}
- Memory entries: {memory_count}

## Interaction Types
1. **workspace** — User needs a full creative workspace (writing, coding, planning)
   - Use for: novels, apps, projects, complex creative work
   - Requires: choosing primitives (CodeEditor, ProseEditor, Kanban, etc.)

2. **view** — User needs to see specific information
   - Use for: "what's on my calendar", "show my notes", "find X"
   - Requires: choosing view type (calendar, list, notes, search)

3. **action** — User wants something done immediately
   - Use for: "add X to list", "remind me", "create event"
   - Requires: specifying action type and parameters

4. **conversation** — User needs dialogue, not tools
   - Use for: questions, emotional support, brainstorming, unclear intent
   - Default when uncertain

5. **hybrid** — User needs action + view together
   - Use for: "add event and show my calendar", "what's this weekend" (show + answer)

## Instructions
Analyze the goal and respond with JSON:

```json
{{
  "interaction_type": "workspace|view|action|conversation|hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "action": {{"type": "...", "params": {{...}}}} or null,
  "view": {{"type": "...", "focus": {{...}}}} or null,
  "workspace": {{"primary": "...", "secondary": [...], "seed_content": {{...}}}} or null,
  "response": "natural language response to user",
  "conversation_mode": "informational|empathetic|collaborative" or null
}}
```

## Examples

Goal: "write a pirate novel with 4 chapters"
→ workspace, primary: ProseEditor, secondary: [Outline], seed_content: {{"outline": ["Chapter 1", ...]}}

Goal: "add milk to grocery list"
→ action, type: add_to_list, params: {{"list": "grocery", "item": "milk"}}

Goal: "what am i doing saturday"
→ hybrid, view: calendar (focused on saturday), response: "You have..."

Goal: "i feel really stressed about work"
→ conversation, mode: empathetic, response: "I hear you..."

Now analyze:'''


@dataclass
class IntentAnalyzer:
    """LLM-driven intent analysis with provider context."""
    
    model: LocalLLM
    calendar: CalendarProvider
    lists: ListProvider
    notes: NotesProvider
    memory: MemoryStore
    
    async def analyze(self, goal: str) -> IntentAnalysis:
        """Analyze user goal and determine appropriate interaction."""
        
        # Gather context about available data
        context = await self._gather_context()
        
        # Build prompt with context
        prompt = INTENT_ANALYSIS_PROMPT.format(
            goal=goal,
            available_lists=", ".join(context["lists"]) or "none",
            event_count=context["event_count"],
            recent_notes_count=context["notes_count"],
            memory_count=context["memory_count"],
        )
        
        # Query LLM
        response = await self.model.generate(
            prompt,
            temperature=0.3,  # Low temperature for consistent classification
            max_tokens=500,
        )
        
        # Parse response
        return self._parse_response(response)
    
    async def _gather_context(self) -> dict[str, Any]:
        """Gather context about available data for the prompt."""
        
        # Get list names
        lists = await self.lists.get_lists()
        
        # Count upcoming events
        now = datetime.now()
        events = await self.calendar.get_events(now, now + timedelta(days=7))
        
        # Count recent notes
        notes = await self.notes.get_recent(limit=10)
        
        # Count relevant memory
        memory_entries = self.memory.query(limit=20)
        
        return {
            "lists": lists,
            "event_count": len(events),
            "notes_count": len(notes),
            "memory_count": len(memory_entries),
        }
    
    def _parse_response(self, response: str) -> IntentAnalysis:
        """Parse LLM JSON response into IntentAnalysis."""
        
        # Extract JSON from response (handle markdown code blocks)
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        
        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            # Fallback to conversation if parsing fails
            return IntentAnalysis(
                interaction_type="conversation",
                confidence=0.5,
                response="I'm not sure I understood. Could you tell me more about what you'd like to do?",
                reasoning="Failed to parse intent, defaulting to conversation",
            )
        
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
            interaction_type=data["interaction_type"],
            confidence=data.get("confidence", 0.8),
            action=action,
            view=view,
            workspace=workspace,
            response=data.get("response"),
            reasoning=data.get("reasoning"),
            conversation_mode=data.get("conversation_mode"),
        )
```

### Interaction Router

```python
# src/sunwell/interface/router.py

from dataclasses import dataclass
from typing import Protocol

from sunwell.interface.types import IntentAnalysis, InteractionType
from sunwell.interface.executor import ActionExecutor
from sunwell.interface.views import ViewRenderer
from sunwell.surface.composer import SurfaceComposer  # RFC-072


class InterfaceOutput(Protocol):
    """Protocol for rendered interface output."""
    pass


@dataclass(frozen=True, slots=True)
class WorkspaceOutput:
    """Full workspace was rendered."""
    layout_id: str
    response: str | None


@dataclass(frozen=True, slots=True)
class ViewOutput:
    """View was rendered."""
    view_type: str
    data: dict
    response: str | None


@dataclass(frozen=True, slots=True)
class ActionOutput:
    """Action was executed."""
    action_type: str
    success: bool
    response: str


@dataclass(frozen=True, slots=True)
class ConversationOutput:
    """Conversation response."""
    response: str
    mode: str | None


@dataclass(frozen=True, slots=True)
class HybridOutput:
    """Combined action + view."""
    action: ActionOutput
    view: ViewOutput


@dataclass
class InteractionRouter:
    """Routes analyzed intent to appropriate handler."""
    
    surface_composer: SurfaceComposer  # RFC-072
    action_executor: ActionExecutor
    view_renderer: ViewRenderer
    
    async def route(self, analysis: IntentAnalysis) -> InterfaceOutput:
        """Route intent analysis to appropriate handler."""
        
        match analysis.interaction_type:
            case "workspace":
                return await self._handle_workspace(analysis)
            case "view":
                return await self._handle_view(analysis)
            case "action":
                return await self._handle_action(analysis)
            case "conversation":
                return await self._handle_conversation(analysis)
            case "hybrid":
                return await self._handle_hybrid(analysis)
            case _:
                # Fallback to conversation
                return ConversationOutput(
                    response=analysis.response or "I'm here to help. What would you like to do?",
                    mode="informational",
                )
    
    async def _handle_workspace(self, analysis: IntentAnalysis) -> WorkspaceOutput:
        """Render a full workspace via RFC-072."""
        
        if not analysis.workspace:
            # Fallback to default workspace
            from sunwell.surface.defaults import default_workspace
            analysis = analysis._replace(workspace=default_workspace())
        
        # Delegate to RFC-072 Surface Composer
        layout_id = await self.surface_composer.compose_from_spec(analysis.workspace)
        
        return WorkspaceOutput(
            layout_id=layout_id,
            response=analysis.response,
        )
    
    async def _handle_view(self, analysis: IntentAnalysis) -> ViewOutput:
        """Render a single-purpose view."""
        
        if not analysis.view:
            return ViewOutput(
                view_type="error",
                data={"message": "No view specified"},
                response=analysis.response,
            )
        
        # Render the view
        view_data = await self.view_renderer.render(analysis.view)
        
        return ViewOutput(
            view_type=analysis.view.type,
            data=view_data,
            response=analysis.response,
        )
    
    async def _handle_action(self, analysis: IntentAnalysis) -> ActionOutput:
        """Execute an action immediately."""
        
        if not analysis.action:
            return ActionOutput(
                action_type="none",
                success=False,
                response="I'm not sure what action to take.",
            )
        
        # Execute the action
        result = await self.action_executor.execute(analysis.action)
        
        return ActionOutput(
            action_type=analysis.action.type,
            success=result.success,
            response=analysis.response or result.message,
        )
    
    async def _handle_conversation(self, analysis: IntentAnalysis) -> ConversationOutput:
        """Return a conversation response."""
        
        return ConversationOutput(
            response=analysis.response or "I'm here to help.",
            mode=analysis.conversation_mode,
        )
    
    async def _handle_hybrid(self, analysis: IntentAnalysis) -> HybridOutput:
        """Handle action + view combination."""
        
        # Execute action first
        action_output = await self._handle_action(analysis)
        
        # Then render view
        view_output = await self._handle_view(analysis)
        
        return HybridOutput(
            action=action_output,
            view=view_output,
        )
```

### Action Executor

```python
# src/sunwell/interface/executor.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sunwell.interface.types import ActionSpec
from sunwell.providers.base import CalendarProvider, ListProvider, CalendarEvent, ListItem


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Result of an executed action."""
    success: bool
    message: str
    data: dict[str, Any] | None = None


@dataclass
class ActionExecutor:
    """Executes actions against data providers."""
    
    calendar: CalendarProvider
    lists: ListProvider
    
    async def execute(self, action: ActionSpec) -> ActionResult:
        """Execute an action and return result."""
        
        match action.type:
            case "add_to_list":
                return await self._add_to_list(action.params)
            case "complete_item":
                return await self._complete_item(action.params)
            case "create_event":
                return await self._create_event(action.params)
            case "create_reminder":
                return await self._create_reminder(action.params)
            case _:
                return ActionResult(
                    success=False,
                    message=f"Unknown action type: {action.type}",
                )
    
    async def _add_to_list(self, params: dict[str, Any]) -> ActionResult:
        """Add an item to a list."""
        
        list_name = params.get("list", "default")
        item_text = params.get("item")
        
        if not item_text:
            return ActionResult(
                success=False,
                message="No item specified to add.",
            )
        
        try:
            item = await self.lists.add_item(list_name, item_text)
            return ActionResult(
                success=True,
                message=f"Added '{item_text}' to {list_name} list.",
                data={"item_id": item.id, "list": list_name},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to add item: {e}",
            )
    
    async def _complete_item(self, params: dict[str, Any]) -> ActionResult:
        """Mark a list item as complete."""
        
        item_id = params.get("item_id")
        
        if not item_id:
            return ActionResult(
                success=False,
                message="No item specified to complete.",
            )
        
        try:
            item = await self.lists.complete_item(item_id)
            return ActionResult(
                success=True,
                message=f"Completed '{item.text}'.",
                data={"item_id": item.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to complete item: {e}",
            )
    
    async def _create_event(self, params: dict[str, Any]) -> ActionResult:
        """Create a calendar event."""
        
        title = params.get("title")
        start = params.get("start")  # ISO string or relative
        duration = params.get("duration_minutes", 60)
        
        if not title or not start:
            return ActionResult(
                success=False,
                message="Event needs a title and start time.",
            )
        
        try:
            # Parse start time
            start_dt = self._parse_datetime(start)
            end_dt = start_dt + timedelta(minutes=duration)
            
            event = CalendarEvent(
                id="",  # Provider will assign
                title=title,
                start=start_dt,
                end=end_dt,
                location=params.get("location"),
                notes=params.get("notes"),
            )
            
            created = await self.calendar.create_event(event)
            return ActionResult(
                success=True,
                message=f"Created event '{title}' for {start_dt.strftime('%A %B %d at %I:%M %p')}.",
                data={"event_id": created.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to create event: {e}",
            )
    
    async def _create_reminder(self, params: dict[str, Any]) -> ActionResult:
        """Create a reminder (implemented as a calendar event with reminder flag)."""
        
        text = params.get("text")
        when = params.get("when")  # "tomorrow", "in 2 hours", ISO string
        
        if not text:
            return ActionResult(
                success=False,
                message="Reminder needs text.",
            )
        
        try:
            remind_at = self._parse_datetime(when or "tomorrow 9am")
            
            event = CalendarEvent(
                id="",
                title=f"🔔 {text}",
                start=remind_at,
                end=remind_at + timedelta(minutes=15),
                notes="Reminder created via Sunwell",
            )
            
            created = await self.calendar.create_event(event)
            return ActionResult(
                success=True,
                message=f"Reminder set: '{text}' for {remind_at.strftime('%A %B %d at %I:%M %p')}.",
                data={"event_id": created.id},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Failed to create reminder: {e}",
            )
    
    def _parse_datetime(self, value: str) -> datetime:
        """Parse datetime from various formats."""
        
        now = datetime.now()
        value_lower = value.lower()
        
        # Relative times
        if value_lower == "tomorrow":
            return now.replace(hour=9, minute=0) + timedelta(days=1)
        if value_lower == "next week":
            return now.replace(hour=9, minute=0) + timedelta(weeks=1)
        if "tomorrow" in value_lower:
            # "tomorrow at 3pm", "tomorrow 3pm"
            base = now + timedelta(days=1)
            return self._parse_time_on_date(base, value_lower)
        if value_lower.startswith("in "):
            # "in 2 hours", "in 30 minutes"
            return self._parse_relative(value_lower[3:], now)
        
        # Try ISO format
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        
        # Default to tomorrow 9am
        return now.replace(hour=9, minute=0) + timedelta(days=1)
    
    def _parse_time_on_date(self, date: datetime, value: str) -> datetime:
        """Parse time component and apply to date."""
        # Simplified - would use dateparser in production
        if "3pm" in value or "3 pm" in value:
            return date.replace(hour=15, minute=0)
        if "9am" in value or "9 am" in value:
            return date.replace(hour=9, minute=0)
        return date.replace(hour=9, minute=0)
    
    def _parse_relative(self, value: str, now: datetime) -> datetime:
        """Parse relative time like '2 hours', '30 minutes'."""
        parts = value.split()
        if len(parts) >= 2:
            try:
                amount = int(parts[0])
                unit = parts[1].lower()
                if unit.startswith("hour"):
                    return now + timedelta(hours=amount)
                if unit.startswith("minute"):
                    return now + timedelta(minutes=amount)
                if unit.startswith("day"):
                    return now + timedelta(days=amount)
            except ValueError:
                pass
        return now + timedelta(hours=1)
```

### Data Providers

#### Base Interfaces

```python
# src/sunwell/providers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A calendar event."""
    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    notes: str | None = None


class CalendarProvider(ABC):
    """Calendar data provider interface."""
    
    @abstractmethod
    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Get events in date range."""
        ...
    
    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new event. Returns event with assigned ID."""
        ...
    
    @abstractmethod
    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        """Update an existing event."""
        ...
    
    @abstractmethod
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event. Returns True if deleted."""
        ...


@dataclass(frozen=True, slots=True)
class ListItem:
    """An item in a list."""
    id: str
    text: str
    completed: bool = False
    list_name: str = "default"
    created: datetime | None = None


class ListProvider(ABC):
    """List/todo data provider interface."""
    
    @abstractmethod
    async def get_lists(self) -> list[str]:
        """Get all list names."""
        ...
    
    @abstractmethod
    async def get_items(self, list_name: str, include_completed: bool = False) -> list[ListItem]:
        """Get items in a list."""
        ...
    
    @abstractmethod
    async def add_item(self, list_name: str, text: str) -> ListItem:
        """Add item to list. Creates list if needed."""
        ...
    
    @abstractmethod
    async def complete_item(self, item_id: str) -> ListItem:
        """Mark item as complete."""
        ...
    
    @abstractmethod
    async def delete_item(self, item_id: str) -> bool:
        """Delete an item."""
        ...


@dataclass(frozen=True, slots=True)
class Note:
    """A note/document."""
    id: str
    title: str
    content: str
    created: datetime
    modified: datetime
    tags: tuple[str, ...] = ()


class NotesProvider(ABC):
    """Notes/documents provider interface."""
    
    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search notes by content."""
        ...
    
    @abstractmethod
    async def get_recent(self, limit: int = 10) -> list[Note]:
        """Get recently modified notes."""
        ...
    
    @abstractmethod
    async def get_by_id(self, note_id: str) -> Note | None:
        """Get a specific note."""
        ...
    
    @abstractmethod
    async def create(self, title: str, content: str, tags: list[str] | None = None) -> Note:
        """Create a new note."""
        ...
    
    @abstractmethod
    async def update(self, note: Note) -> Note:
        """Update an existing note."""
        ...
```

#### Sunwell Native Implementations

```python
# src/sunwell/providers/native/calendar.py

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sunwell.providers.base import CalendarProvider, CalendarEvent


class SunwellCalendar(CalendarProvider):
    """Sunwell-native calendar stored in .sunwell/calendar.json"""
    
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "calendar.json"
        self._ensure_exists()
    
    def _ensure_exists(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]")
    
    def _load(self) -> list[dict]:
        return json.loads(self.path.read_text())
    
    def _save(self, events: list[dict]) -> None:
        self.path.write_text(json.dumps(events, default=str, indent=2))
    
    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        data = self._load()
        events = []
        
        for e in data:
            event_start = datetime.fromisoformat(e["start"])
            if start <= event_start <= end:
                events.append(CalendarEvent(
                    id=e["id"],
                    title=e["title"],
                    start=event_start,
                    end=datetime.fromisoformat(e["end"]),
                    location=e.get("location"),
                    notes=e.get("notes"),
                ))
        
        return sorted(events, key=lambda e: e.start)
    
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        data = self._load()
        
        new_event = CalendarEvent(
            id=str(uuid4()),
            title=event.title,
            start=event.start,
            end=event.end,
            location=event.location,
            notes=event.notes,
        )
        
        data.append({
            "id": new_event.id,
            "title": new_event.title,
            "start": new_event.start.isoformat(),
            "end": new_event.end.isoformat(),
            "location": new_event.location,
            "notes": new_event.notes,
        })
        
        self._save(data)
        return new_event
    
    async def update_event(self, event: CalendarEvent) -> CalendarEvent:
        data = self._load()
        
        for i, e in enumerate(data):
            if e["id"] == event.id:
                data[i] = {
                    "id": event.id,
                    "title": event.title,
                    "start": event.start.isoformat(),
                    "end": event.end.isoformat(),
                    "location": event.location,
                    "notes": event.notes,
                }
                break
        
        self._save(data)
        return event
    
    async def delete_event(self, event_id: str) -> bool:
        data = self._load()
        original_len = len(data)
        data = [e for e in data if e["id"] != event_id]
        self._save(data)
        return len(data) < original_len


# src/sunwell/providers/native/lists.py

class SunwellLists(ListProvider):
    """Sunwell-native lists stored in .sunwell/lists/"""
    
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "lists"
        self.dir.mkdir(parents=True, exist_ok=True)
    
    def _list_path(self, name: str) -> Path:
        return self.dir / f"{name}.json"
    
    def _load_list(self, name: str) -> list[dict]:
        path = self._list_path(name)
        if path.exists():
            return json.loads(path.read_text())
        return []
    
    def _save_list(self, name: str, items: list[dict]) -> None:
        self._list_path(name).write_text(json.dumps(items, indent=2))
    
    async def get_lists(self) -> list[str]:
        return [f.stem for f in self.dir.glob("*.json")]
    
    async def get_items(self, list_name: str, include_completed: bool = False) -> list[ListItem]:
        items = self._load_list(list_name)
        result = []
        
        for item in items:
            if include_completed or not item.get("completed", False):
                result.append(ListItem(
                    id=item["id"],
                    text=item["text"],
                    completed=item.get("completed", False),
                    list_name=list_name,
                    created=datetime.fromisoformat(item["created"]) if item.get("created") else None,
                ))
        
        return result
    
    async def add_item(self, list_name: str, text: str) -> ListItem:
        items = self._load_list(list_name)
        
        new_item = {
            "id": str(uuid4()),
            "text": text,
            "completed": False,
            "created": datetime.now().isoformat(),
        }
        
        items.append(new_item)
        self._save_list(list_name, items)
        
        return ListItem(
            id=new_item["id"],
            text=text,
            completed=False,
            list_name=list_name,
            created=datetime.fromisoformat(new_item["created"]),
        )
    
    async def complete_item(self, item_id: str) -> ListItem:
        # Search all lists for the item
        for list_name in await self.get_lists():
            items = self._load_list(list_name)
            
            for item in items:
                if item["id"] == item_id:
                    item["completed"] = True
                    self._save_list(list_name, items)
                    return ListItem(
                        id=item["id"],
                        text=item["text"],
                        completed=True,
                        list_name=list_name,
                    )
        
        raise ValueError(f"Item not found: {item_id}")
    
    async def delete_item(self, item_id: str) -> bool:
        for list_name in await self.get_lists():
            items = self._load_list(list_name)
            original_len = len(items)
            items = [i for i in items if i["id"] != item_id]
            
            if len(items) < original_len:
                self._save_list(list_name, items)
                return True
        
        return False


# src/sunwell/providers/native/notes.py

class SunwellNotes(NotesProvider):
    """Sunwell-native notes stored as markdown in .sunwell/notes/"""
    
    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir / "notes"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "_index.json"
    
    def _load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {}
    
    def _save_index(self, index: dict[str, dict]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2))
    
    async def search(self, query: str, limit: int = 10) -> list[Note]:
        index = self._load_index()
        results = []
        query_lower = query.lower()
        
        for note_id, meta in index.items():
            note_path = self.dir / f"{note_id}.md"
            if note_path.exists():
                content = note_path.read_text()
                
                # Simple search: title or content contains query
                if query_lower in meta["title"].lower() or query_lower in content.lower():
                    results.append(Note(
                        id=note_id,
                        title=meta["title"],
                        content=content,
                        created=datetime.fromisoformat(meta["created"]),
                        modified=datetime.fromisoformat(meta["modified"]),
                        tags=tuple(meta.get("tags", [])),
                    ))
        
        # Sort by relevance (title match > content match) then by modified
        results.sort(key=lambda n: (query_lower not in n.title.lower(), -n.modified.timestamp()))
        return results[:limit]
    
    async def get_recent(self, limit: int = 10) -> list[Note]:
        index = self._load_index()
        
        # Sort by modified time descending
        sorted_ids = sorted(
            index.keys(),
            key=lambda k: index[k]["modified"],
            reverse=True,
        )[:limit]
        
        results = []
        for note_id in sorted_ids:
            note = await self.get_by_id(note_id)
            if note:
                results.append(note)
        
        return results
    
    async def get_by_id(self, note_id: str) -> Note | None:
        index = self._load_index()
        
        if note_id not in index:
            return None
        
        meta = index[note_id]
        note_path = self.dir / f"{note_id}.md"
        
        if not note_path.exists():
            return None
        
        return Note(
            id=note_id,
            title=meta["title"],
            content=note_path.read_text(),
            created=datetime.fromisoformat(meta["created"]),
            modified=datetime.fromisoformat(meta["modified"]),
            tags=tuple(meta.get("tags", [])),
        )
    
    async def create(self, title: str, content: str, tags: list[str] | None = None) -> Note:
        index = self._load_index()
        
        note_id = str(uuid4())
        now = datetime.now()
        
        # Save content
        note_path = self.dir / f"{note_id}.md"
        note_path.write_text(content)
        
        # Update index
        index[note_id] = {
            "title": title,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "tags": tags or [],
        }
        self._save_index(index)
        
        return Note(
            id=note_id,
            title=title,
            content=content,
            created=now,
            modified=now,
            tags=tuple(tags or []),
        )
    
    async def update(self, note: Note) -> Note:
        index = self._load_index()
        
        if note.id not in index:
            raise ValueError(f"Note not found: {note.id}")
        
        now = datetime.now()
        
        # Save content
        note_path = self.dir / f"{note.id}.md"
        note_path.write_text(note.content)
        
        # Update index
        index[note.id] = {
            "title": note.title,
            "created": index[note.id]["created"],
            "modified": now.isoformat(),
            "tags": list(note.tags),
        }
        self._save_index(index)
        
        return Note(
            id=note.id,
            title=note.title,
            content=note.content,
            created=note.created,
            modified=now,
            tags=note.tags,
        )
```

### Provider Registry

```python
# src/sunwell/providers/registry.py

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, Type

from sunwell.providers.base import CalendarProvider, ListProvider, NotesProvider
from sunwell.providers.native.calendar import SunwellCalendar
from sunwell.providers.native.lists import SunwellLists
from sunwell.providers.native.notes import SunwellNotes


T = TypeVar("T")


@dataclass
class ProviderRegistry:
    """Registry for data providers.
    
    Allows swapping implementations (Sunwell native vs external integrations).
    """
    
    _calendar: CalendarProvider | None = None
    _lists: ListProvider | None = None
    _notes: NotesProvider | None = None
    
    @classmethod
    def create_default(cls, data_dir: Path) -> "ProviderRegistry":
        """Create registry with Sunwell-native providers."""
        return cls(
            _calendar=SunwellCalendar(data_dir),
            _lists=SunwellLists(data_dir),
            _notes=SunwellNotes(data_dir),
        )
    
    @property
    def calendar(self) -> CalendarProvider:
        if not self._calendar:
            raise RuntimeError("Calendar provider not configured")
        return self._calendar
    
    @property
    def lists(self) -> ListProvider:
        if not self._lists:
            raise RuntimeError("Lists provider not configured")
        return self._lists
    
    @property
    def notes(self) -> NotesProvider:
        if not self._notes:
            raise RuntimeError("Notes provider not configured")
        return self._notes
    
    def register_calendar(self, provider: CalendarProvider) -> None:
        """Register a calendar provider (e.g., Google Calendar)."""
        self._calendar = provider
    
    def register_lists(self, provider: ListProvider) -> None:
        """Register a lists provider (e.g., Todoist)."""
        self._lists = provider
    
    def register_notes(self, provider: NotesProvider) -> None:
        """Register a notes provider (e.g., Obsidian)."""
        self._notes = provider
```

---

## Svelte Integration

### Interface Store

```typescript
// studio/src/stores/interface.svelte.ts

/**
 * Interface Store — Generative Interface state management (RFC-075)
 */

import { invoke } from '@tauri-apps/api/core';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type InteractionType = 'workspace' | 'view' | 'action' | 'conversation' | 'hybrid';

export interface IntentAnalysis {
  interaction_type: InteractionType;
  confidence: number;
  action?: ActionSpec;
  view?: ViewSpec;
  workspace?: WorkspaceSpec;
  response?: string;
  reasoning?: string;
  conversation_mode?: 'informational' | 'empathetic' | 'collaborative';
}

export interface ActionSpec {
  type: string;
  params: Record<string, unknown>;
}

export interface ViewSpec {
  type: 'calendar' | 'list' | 'notes' | 'search';
  focus?: Record<string, unknown>;
  query?: string;
}

export interface WorkspaceSpec {
  primary: string;
  secondary: string[];
  contextual: string[];
  arrangement: string;
  seed_content?: Record<string, unknown>;
}

export interface InterfaceOutput {
  type: InteractionType;
  response?: string;
  data?: Record<string, unknown>;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface InterfaceState {
  /** Current output being displayed */
  current: InterfaceOutput | null;
  
  /** Is analysis in progress */
  isAnalyzing: boolean;
  
  /** Last analysis result (for debugging) */
  lastAnalysis: IntentAnalysis | null;
  
  /** Conversation history */
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
  }>;
  
  /** Error state */
  error: string | null;
}

function createInitialState(): InterfaceState {
  return {
    current: null,
    isAnalyzing: false,
    lastAnalysis: null,
    messages: [],
    error: null,
  };
}

export let interfaceState = $state<InterfaceState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Process user input through the generative interface.
 */
export async function processInput(input: string): Promise<InterfaceOutput | null> {
  interfaceState.isAnalyzing = true;
  interfaceState.error = null;
  
  // Add user message
  interfaceState.messages.push({
    role: 'user',
    content: input,
    timestamp: Date.now(),
  });
  
  try {
    // Call Python via Tauri
    const result = await invoke<InterfaceOutput>('process_goal', { goal: input });
    
    interfaceState.current = result;
    
    // Add assistant response
    if (result.response) {
      interfaceState.messages.push({
        role: 'assistant',
        content: result.response,
        timestamp: Date.now(),
      });
    }
    
    return result;
  } catch (e) {
    interfaceState.error = e instanceof Error ? e.message : String(e);
    console.error('Interface processing failed:', e);
    return null;
  } finally {
    interfaceState.isAnalyzing = false;
  }
}

/**
 * Clear conversation history.
 */
export function clearHistory(): void {
  interfaceState.messages = [];
}

/**
 * Reset to initial state.
 */
export function resetInterface(): void {
  Object.assign(interfaceState, createInitialState());
}
```

### Input Component

```svelte
<!-- studio/src/components/GoalInput.svelte -->
<script lang="ts">
  import { processInput, interfaceState } from '../stores/interface.svelte';
  
  let inputValue = $state('');
  let inputEl: HTMLInputElement;
  
  async function handleSubmit() {
    const goal = inputValue.trim();
    if (!goal) return;
    
    inputValue = '';
    await processInput(goal);
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<div class="goal-input" class:analyzing={interfaceState.isAnalyzing}>
  <input
    bind:this={inputEl}
    bind:value={inputValue}
    onkeydown={handleKeydown}
    placeholder="What would you like to do?"
    disabled={interfaceState.isAnalyzing}
  />
  
  <button 
    onclick={handleSubmit}
    disabled={interfaceState.isAnalyzing || !inputValue.trim()}
  >
    {#if interfaceState.isAnalyzing}
      <span class="spinner"></span>
    {:else}
      →
    {/if}
  </button>
</div>

<style>
  .goal-input {
    display: flex;
    gap: var(--spacing-sm);
    padding: var(--spacing-md);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-subtle);
    transition: border-color 0.2s;
  }
  
  .goal-input:focus-within {
    border-color: var(--gold);
  }
  
  .goal-input.analyzing {
    opacity: 0.8;
  }
  
  input {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: var(--font-size-md);
    outline: none;
  }
  
  input::placeholder {
    color: var(--text-tertiary);
  }
  
  button {
    padding: var(--spacing-sm) var(--spacing-md);
    background: var(--gold);
    color: var(--bg-primary);
    border: none;
    border-radius: var(--radius-md);
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--bg-primary);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
```

---

## Rust Layer

```rust
// studio/src-tauri/src/interface.rs

use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfaceOutput {
    #[serde(rename = "type")]
    pub output_type: String,
    pub response: Option<String>,
    pub data: Option<serde_json::Value>,
}

/// Process a user goal through the generative interface.
#[tauri::command]
pub async fn process_goal(goal: String) -> Result<InterfaceOutput, String> {
    let output = Command::new("sunwell")
        .args(["interface", "process", "--goal", &goal, "--json"])
        .output()
        .map_err(|e| format!("Failed to process goal: {}", e))?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Processing failed: {}", stderr));
    }
    
    serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse output: {}", e))
}
```

---

## CLI Commands

```python
# src/sunwell/cli/interface.py

import asyncio
import json
from pathlib import Path

import click


@click.group()
def interface() -> None:
    """Generative interface commands (RFC-075)."""
    pass


@interface.command("process")
@click.option("--goal", required=True, help="User goal to process")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--data-dir", default=None, help="Data directory path")
def process(goal: str, json_output: bool, data_dir: str | None) -> None:
    """Process a goal through the generative interface."""
    asyncio.run(_process(goal, json_output, data_dir))


async def _process(goal: str, json_output: bool, data_dir_str: str | None) -> None:
    from sunwell.interface.analyzer import IntentAnalyzer
    from sunwell.interface.router import InteractionRouter
    from sunwell.interface.executor import ActionExecutor
    from sunwell.interface.views import ViewRenderer
    from sunwell.providers.registry import ProviderRegistry
    from sunwell.memory.store import MemoryStore
    from sunwell.llm.local import LocalLLM
    from sunwell.surface.composer import SurfaceComposer
    
    # Setup data directory
    data_dir = Path(data_dir_str) if data_dir_str else Path.cwd() / ".sunwell"
    
    # Initialize providers
    providers = ProviderRegistry.create_default(data_dir)
    
    # Initialize memory
    memory = MemoryStore.load(data_dir / "memory")
    
    # Initialize LLM
    llm = LocalLLM.load_default()
    
    # Build analyzer
    analyzer = IntentAnalyzer(
        model=llm,
        calendar=providers.calendar,
        lists=providers.lists,
        notes=providers.notes,
        memory=memory,
    )
    
    # Analyze intent
    analysis = await analyzer.analyze(goal)
    
    # Build router
    router = InteractionRouter(
        surface_composer=SurfaceComposer(...),  # RFC-072
        action_executor=ActionExecutor(
            calendar=providers.calendar,
            lists=providers.lists,
        ),
        view_renderer=ViewRenderer(providers),
    )
    
    # Route to appropriate handler
    output = await router.route(analysis)
    
    # Output result
    if json_output:
        result = {
            "type": output.__class__.__name__.replace("Output", "").lower(),
            "response": getattr(output, "response", None),
            "data": getattr(output, "data", None),
        }
        click.echo(json.dumps(result))
    else:
        click.echo(f"Type: {output.__class__.__name__}")
        if hasattr(output, "response") and output.response:
            click.echo(f"Response: {output.response}")
```

---

## Implementation Plan

### Phase 1: Core Types & Providers (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `src/sunwell/interface/types.py` | High | Small |
| Create `src/sunwell/providers/base.py` | High | Small |
| Implement `SunwellCalendar` | High | Medium |
| Implement `SunwellLists` | High | Medium |
| Implement `SunwellNotes` | High | Medium |
| Create `ProviderRegistry` | High | Small |

### Phase 2: Intent Analysis (3-4 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `IntentAnalyzer` class | High | Large |
| Design prompt for intent classification | High | Medium |
| Implement JSON parsing with fallbacks | High | Medium |
| Add context gathering (available data) | Medium | Small |
| Test with diverse goal examples | High | Medium |

### Phase 3: Routing & Execution (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create `InteractionRouter` | High | Medium |
| Implement `ActionExecutor` | High | Medium |
| Create `ViewRenderer` (basic) | Medium | Medium |
| Wire up RFC-072 for workspace routing | High | Small |
| Add datetime parsing for actions | Medium | Small |

### Phase 4: Integration (2-3 days)

| Task | Priority | Effort |
|------|----------|--------|
| Create Rust `interface.rs` module | High | Small |
| Add `process_goal` Tauri command | High | Small |
| Create Svelte interface store | High | Medium |
| Create `GoalInput` component | High | Medium |
| Wire up to existing Studio shell | High | Medium |

### Phase 5: Polish (1-2 days)

| Task | Priority | Effort |
|------|----------|--------|
| Add toast notifications for actions | Medium | Small |
| Add conversation history UI | Medium | Medium |
| Add "why this?" reasoning display | Low | Small |
| Error handling and fallbacks | High | Medium |

---

## Testing Strategy

### Python Tests

```python
# tests/test_intent_analyzer.py

@pytest.mark.asyncio
async def test_action_intent():
    """'add to list' should be classified as action."""
    analyzer = create_test_analyzer()
    result = await analyzer.analyze("add milk to grocery list")
    
    assert result.interaction_type == "action"
    assert result.action is not None
    assert result.action.type == "add_to_list"
    assert result.action.params["item"] == "milk"


@pytest.mark.asyncio
async def test_workspace_intent():
    """'write a novel' should be classified as workspace."""
    analyzer = create_test_analyzer()
    result = await analyzer.analyze("write a pirate novel with 4 chapters")
    
    assert result.interaction_type == "workspace"
    assert result.workspace is not None
    assert result.workspace.primary == "ProseEditor"


@pytest.mark.asyncio
async def test_conversation_intent():
    """Emotional support should be classified as conversation."""
    analyzer = create_test_analyzer()
    result = await analyzer.analyze("i feel really stressed about work")
    
    assert result.interaction_type == "conversation"
    assert result.conversation_mode == "empathetic"


@pytest.mark.asyncio
async def test_hybrid_intent():
    """Calendar question should be hybrid (view + response)."""
    analyzer = create_test_analyzer()
    result = await analyzer.analyze("what am i doing this weekend")
    
    assert result.interaction_type in ("hybrid", "view")
    assert result.view is not None
    assert result.view.type == "calendar"
    assert result.response is not None


# tests/test_action_executor.py

@pytest.mark.asyncio
async def test_add_to_list():
    """Adding item to list should succeed."""
    lists = SunwellLists(tmp_path)
    executor = ActionExecutor(calendar=..., lists=lists)
    
    result = await executor.execute(ActionSpec(
        type="add_to_list",
        params={"list": "grocery", "item": "broccoli"},
    ))
    
    assert result.success
    assert "broccoli" in result.message
    
    # Verify item was added
    items = await lists.get_items("grocery")
    assert any(i.text == "broccoli" for i in items)
```

---

## Performance Considerations

| Operation | Target | Notes |
|-----------|--------|-------|
| Intent analysis (LLM) | 500-1500ms | Primary latency source; 3B model on CPU |
| Context gathering | <100ms | Parallel provider queries |
| Action execution | <50ms | Local file operations |
| View rendering | <100ms | Data fetching + formatting |
| Total round-trip | <2000ms | Acceptable for conversational UI |

**Optimizations:**
- Cache provider context between requests
- Use streaming LLM output for progressive response
- Pre-warm LLM model on app start
- Consider GPU acceleration for LLM if available

---

## Security Considerations

1. **Action scope** — Actions only affect Sunwell-native data (local files)
2. **No external execution** — Cannot run arbitrary shell commands
3. **Data isolation** — Each project has isolated `.sunwell/` directory
4. **No network in v1** — All providers are local; external integrations require explicit auth later
5. **LLM is local** — No data sent to external services for intent analysis

---

## Open Questions

| Question | Current Decision | Notes |
|----------|------------------|-------|
| Should actions require confirmation? | No (use undo instead) | Faster UX; add confirmation for destructive actions later |
| How to handle multi-turn conversations? | Simple history, no complex state | Keep it simple for v1 |
| Should analysis explain reasoning to user? | Optional "why?" button | Don't clutter UI by default |
| What if LLM is slow on weak hardware? | Fallback to simpler classifier | Could train tiny intent classifier as fallback |

---

## Future Extensions

1. **External integrations** — Google Calendar, Todoist, Obsidian via provider interfaces
2. **Voice input** — Speech-to-text before intent analysis
3. **Proactive suggestions** — "You have a meeting in 10 minutes"
4. **Multi-turn planning** — Complex goal decomposition
5. **Custom actions** — User-defined automations
6. **Shared context** — Cross-project memory and preferences

---

## References

- RFC-043 — Sunwell Studio (GUI framework)
- RFC-061 — Holy Light Design System (visual styling)
- RFC-065 — Unified Memory (context and learnings)
- RFC-072 — Surface Primitives (workspace rendering, renamed)
- `src/sunwell/memory/store.py` — MemoryStore for context
- `src/sunwell/llm/local.py` — Local LLM wrapper (to be created)

---

## Appendix: Example Interactions

### Action: Add to List

```
User: "add broccoli to my grocery list"

Analysis:
  interaction_type: action
  action: { type: add_to_list, params: { list: grocery, item: broccoli } }
  response: "Added broccoli to your grocery list."

Output:
  Toast: "✓ Added broccoli to grocery list"
```

### View: Calendar Query

```
User: "what am i doing this weekend"

Analysis:
  interaction_type: hybrid
  view: { type: calendar, focus: { start: 2026-01-24, end: 2026-01-26 } }
  response: "This weekend you have dinner with Sarah on Saturday evening."

Output:
  Calendar view (focused on Jan 24-26) + response text
```

### Workspace: Creative Project

```
User: "write a pirate novel with 4 chapters"

Analysis:
  interaction_type: workspace
  workspace: {
    primary: ProseEditor,
    secondary: [Outline],
    seed_content: { outline: ["Chapter 1: The Map", "Chapter 2: The Voyage", ...] }
  }
  response: "I've set up a writing workspace for your pirate novel. The outline has 4 chapters ready for you."

Output:
  Full workspace: ProseEditor (main) + Outline sidebar (pre-populated)
```

### Conversation: Emotional Support

```
User: "i feel really stressed about work"

Analysis:
  interaction_type: conversation
  conversation_mode: empathetic
  response: "I hear you — work stress can be really overwhelming. Would you like to talk about what's going on, or would it help to take a break and do something creative?"

Output:
  Chat response (no tools, empathetic tone)
```

### Conversation: Simple Question

```
User: "what's the capital of France"

Analysis:
  interaction_type: conversation
  conversation_mode: informational
  response: "Paris is the capital of France."

Output:
  Chat response (quick answer)
```
