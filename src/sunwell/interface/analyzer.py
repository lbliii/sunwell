"""Intent Analyzer (RFC-075).

LLM-driven intent analysis with provider context.
Analyzes user goals and determines the appropriate interaction type.

Extended in RFC-079 to accept ProjectAnalysis context for project-aware routing.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sunwell.interface.types import (
    ActionSpec,
    IntentAnalysis,
    ViewSpec,
)
from sunwell.providers.base import (
    BookmarksProvider,
    CalendarProvider,
    ContactsProvider,
    FilesProvider,
    GitProvider,
    HabitsProvider,
    ListProvider,
    NotesProvider,
    ProjectsProvider,
)
from sunwell.surface.types import WorkspaceSpec

if TYPE_CHECKING:
    from sunwell.project.intent_types import ProjectAnalysis

# Prompt is split into parts for readability
_PROMPT_HEADER = '''Analyze this user goal and determine the best way to help.

## User Goal
"{goal}"

## Available Context
- Lists: {available_lists}
- Upcoming events (next 7 days): {event_count}
- Recent notes: {recent_notes_count}
- Projects available: {projects_available}
- Files accessible: {files_accessible}
- Git repository: {git_available}
- Bookmarks: {bookmarks_count}
- Habits tracked: {habits_count}
- Contacts: {contacts_count}

## Interaction Types
1. **workspace** — Full creative workspace (writing, coding, planning)
2. **view** — Display specific information (calendar, list, notes, files, projects)
3. **action** — Execute immediately (add to list, create event)
4. **conversation** — Dialogue (questions, emotional support, explanations)
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
- table: {{data_source, columns}} — Tabular data view
- preview: {{file_path}} — File preview (markdown, code, image)
- diff: {{left_path, right_path}} — Compare two files
- files: {{path, recursive}} — File listing
- projects: {{query}} — Project listing/search
- git_status: {{}} — Repository status (branch, changes)
- git_log: {{limit}} — Commit history
- git_branches: {{}} — Branch listing
- bookmarks: {{query, tag}} — Bookmark search
- habits: {{}} — Habit tracking overview
- contacts: {{query}} — Contact search

## Workspace Primitives
CodeEditor, ProseEditor, Kanban, Terminal, FileTree, Outline, DataTable, Preview, DiffView, Timeline

## Auxiliary Panels (for conversation mode)
Panel types available:
- calendar: {{focus_date}} — Calendar view
- tasks: {{list_name}} — Task/todo list
- chart: {{chart_type, data_hint}} — Data visualization (line, bar, pie)
- image: {{query, alt}} — Visual aid (diagram, illustration)
- upload: {{accept, purpose}} — File upload prompt
- code: {{language, snippet}} — Code block with syntax highlighting
- map: {{query}} — Location/geographic reference
- editor: {{content}} — Editable text panel
- document: {{file_info}} — Document preview
- products: {{items}} — Product comparison list
- links: {{resources}} — Related resources/references

## COMPOSITION RULES — WHEN TO ADD PANELS
CRITICAL: Match intent signals to panels:

| Intent Signal | Required Panels | Input Tools |
|---------------|-----------------|-------------|
| "plan my week/day", "schedule", day names, times | calendar | - |
| "todo", "tasks", "remind me", "checklist" | tasks | - |
| "budget", "spending", "money", "finances" | chart + upload | upload |
| "how does X work", "explain", "what is" | image + links | - |
| "where is", "near me", "directions" | map | location |
| "write a story/poem", "draft", "creative" | editor | voice |
| user uploads image | image (preview) | camera, upload |
| "code", "function", programming terms | code | - |
| "workout", "steps", "calories", "health" | chart | - |
| "buy", "compare products", "shopping" | products | - |
| user uploads document | document | upload |

ALWAYS add a panel when the intent signal is present.
Generic chat (greetings, emotional) = NO panels.

## Suggested Input Tools
- upload: Files/documents would help (finances, documents)
- camera: Photo capture useful (receipts, items)
- voice: Voice easier (creative writing, dictation)
- location: Current location useful (maps, nearby searches)
- draw: Freeform annotation useful (diagrams, sketches)

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
  "conversation_mode": "informational|empathetic|collaborative" or null,
  "auxiliary_panels": [{{"panel_type": "...", "title": "...", "data": {{...}}}}] or [],
  "suggested_tools": ["upload", "camera", ...] or []
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
    files: FilesProvider | None = None
    projects: ProjectsProvider | None = None
    git: GitProvider | None = None
    bookmarks: BookmarksProvider | None = None
    habits: HabitsProvider | None = None
    contacts: ContactsProvider | None = None

    async def analyze(
        self,
        goal: str,
        project_context: ProjectAnalysis | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> IntentAnalysis:
        """Analyze user goal and determine appropriate interaction.

        Args:
            goal: User's stated goal or intent.
            project_context: Optional ProjectAnalysis from RFC-079 for
                project-aware routing. When provided, augments context
                with project type, current pipeline step, and confidence.
            conversation_history: Optional list of prior messages for
                multi-turn conversation continuity. Each message has
                'role' (user/assistant) and 'content' keys.

        Returns:
            IntentAnalysis with interaction type and workspace/action specs.
        """
        # Gather context about available data
        context = await self._gather_context()

        # Augment with project context if available (RFC-079)
        if project_context:
            context["project_type"] = project_context.project_type.value
            context["project_subtype"] = project_context.project_subtype
            context["current_pipeline_step"] = project_context.current_step
            context["project_confidence"] = project_context.confidence
            context["suggested_workspace"] = project_context.suggested_workspace_primary

        # Build prompt with context
        prompt = _PROMPT_HEADER.format(
            goal=goal,
            available_lists=", ".join(context["lists"]) or "none",
            event_count=context["event_count"],
            recent_notes_count=context["notes_count"],
            projects_available="yes" if context["projects_available"] else "no",
            files_accessible="yes" if context["files_accessible"] else "no",
            git_available="yes" if context["git_available"] else "no",
            bookmarks_count=context["bookmarks_count"],
            habits_count=context["habits_count"],
            contacts_count=context["contacts_count"],
        )

        # Add conversation history for multi-turn context
        if conversation_history:
            history_text = "\n\n## Conversation History\n"
            for msg in conversation_history[-6:]:  # Last 6 messages max
                role = msg.get("role", "user").title()
                content = msg.get("content", "")[:500]  # Truncate long messages
                history_text += f"**{role}**: {content}\n"
            history_text += "\n(Continue this conversation naturally)\n"
            prompt = prompt.replace("Now analyze the goal:", history_text + "Now analyze the goal:")

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
        projects_available = False
        files_accessible = False
        git_available = False
        bookmarks_count = 0

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

        # Check if projects provider is available
        if self.projects:
            with contextlib.suppress(Exception):
                project_list = await self.projects.list_projects()
                projects_available = len(project_list) > 0

        # Check if files provider is available
        if self.files:
            with contextlib.suppress(Exception):
                file_list = await self.files.list_files(".", recursive=False)
                files_accessible = len(file_list) > 0

        # Check if git provider is available
        if self.git:
            with contextlib.suppress(Exception):
                status = await self.git.get_status()
                git_available = status.branch != "unknown"

        # Count bookmarks
        if self.bookmarks:
            with contextlib.suppress(Exception):
                recent_bookmarks = await self.bookmarks.get_recent(limit=10)
                bookmarks_count = len(recent_bookmarks)

        # Count habits
        habits_count = 0
        if self.habits:
            with contextlib.suppress(Exception):
                habit_list = await self.habits.list_habits()
                habits_count = len(habit_list)

        # Count contacts
        contacts_count = 0
        if self.contacts:
            with contextlib.suppress(Exception):
                contact_list = await self.contacts.list_contacts(limit=10)
                contacts_count = len(contact_list)

        return {
            "lists": lists,
            "event_count": event_count,
            "notes_count": notes_count,
            "projects_available": projects_available,
            "files_accessible": files_accessible,
            "git_available": git_available,
            "bookmarks_count": bookmarks_count,
            "habits_count": habits_count,
            "contacts_count": contacts_count,
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

        # Parse auxiliary panels for conversation mode
        auxiliary_panels = []
        for panel_data in data.get("auxiliary_panels", []):
            if isinstance(panel_data, dict) and panel_data.get("panel_type"):
                auxiliary_panels.append(panel_data)

        # Parse suggested tools
        suggested_tools = data.get("suggested_tools", [])
        if not isinstance(suggested_tools, list):
            suggested_tools = []

        return IntentAnalysis(
            interaction_type=data.get("interaction_type", "conversation"),
            confidence=data.get("confidence", 0.8),
            action=action,
            view=view,
            workspace=workspace,
            response=data.get("response"),
            reasoning=data.get("reasoning"),
            conversation_mode=data.get("conversation_mode"),
            auxiliary_panels=tuple(auxiliary_panels),
            suggested_tools=tuple(suggested_tools),
        )
