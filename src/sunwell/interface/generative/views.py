"""View Renderer (RFC-075, RFC-078).

Renders views for calendar, lists, notes, files, projects, and search.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sunwell.interface.generative.types import ViewSpec
from sunwell.models.providers.registry import ProviderRegistry

# =============================================================================
# FILE EXTENSION CONSTANTS — Avoid recreation per call
# =============================================================================

_MARKDOWN_EXTS: frozenset[str] = frozenset({"md", "markdown", "mdown", "mkd"})
_CODE_EXTS: frozenset[str] = frozenset({
    "py", "js", "ts", "jsx", "tsx", "rs", "go", "java", "c", "cpp",
    "h", "hpp", "cs", "rb", "php", "swift", "kt", "scala", "sh",
    "bash", "zsh", "fish", "ps1", "yaml", "yml", "json", "toml",
    "xml", "html", "css", "scss", "sass", "less", "sql", "graphql",
})
_IMAGE_EXTS: frozenset[str] = frozenset({"png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp"})
_PDF_EXTS: frozenset[str] = frozenset({"pdf"})

_EXT_TO_LANGUAGE: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "javascript",
    "tsx": "typescript",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cs": "csharp",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin",
    "scala": "scala",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "toml": "toml",
    "xml": "xml",
    "html": "html",
    "css": "css",
    "scss": "scss",
    "sql": "sql",
}


@dataclass(slots=True)
class ViewRenderer:
    """Renders views based on ViewSpec."""

    providers: ProviderRegistry

    async def render(self, spec: ViewSpec) -> dict[str, Any]:
        """Render a view and return its data."""
        match spec.type:
            case "calendar":
                return await self._render_calendar(spec)
            case "list":
                return await self._render_list(spec)
            case "notes":
                return await self._render_notes(spec)
            case "search":
                return await self._render_search(spec)
            case "table":
                return await self._render_table(spec)
            case "preview":
                return await self._render_preview(spec)
            case "diff":
                return await self._render_diff(spec)
            case "files":
                return await self._render_files(spec)
            case "projects":
                return await self._render_projects(spec)
            case "git_status":
                return await self._render_git_status(spec)
            case "git_log":
                return await self._render_git_log(spec)
            case "git_branches":
                return await self._render_git_branches(spec)
            case "bookmarks":
                return await self._render_bookmarks(spec)
            case "habits":
                return await self._render_habits(spec)
            case "contacts":
                return await self._render_contacts(spec)
            case _:
                return {"error": f"Unknown view type: {spec.type}"}

    async def _render_calendar(self, spec: ViewSpec) -> dict[str, Any]:
        """Render calendar view."""
        if not self.providers.has_calendar():
            return {"error": "Calendar provider not configured", "events": []}

        focus = spec.focus or {}

        # Parse date range
        start = self._parse_date(focus.get("start"))
        end = self._parse_date(focus.get("end"))

        # Default to next 7 days if no range specified
        if start is None:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if end is None:
            end = start + timedelta(days=7)

        events = await self.providers.calendar.get_events(start, end)

        return {
            "type": "calendar",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "events": [e.to_dict() for e in events],
            "event_count": len(events),
        }

    async def _render_list(self, spec: ViewSpec) -> dict[str, Any]:
        """Render list view."""
        if not self.providers.has_lists():
            return {"error": "Lists provider not configured", "items": []}

        focus = spec.focus or {}
        list_name = focus.get("list_name", "default")
        include_completed = focus.get("include_completed", False)

        items = await self.providers.lists.get_items(list_name, include_completed)

        return {
            "type": "list",
            "list_name": list_name,
            "items": [i.to_dict() for i in items],
            "item_count": len(items),
            "completed_count": sum(1 for i in items if i.completed),
        }

    async def _render_notes(self, spec: ViewSpec) -> dict[str, Any]:
        """Render notes view."""
        if not self.providers.has_notes():
            return {"error": "Notes provider not configured", "notes": []}

        focus = spec.focus or {}

        if focus.get("search"):
            notes = await self.providers.notes.search(focus["search"])
            return {
                "type": "notes",
                "mode": "search",
                "query": focus["search"],
                "notes": [n.to_dict() for n in notes],
                "note_count": len(notes),
            }
        else:
            limit = focus.get("limit", 10)
            notes = await self.providers.notes.get_recent(limit)
            return {
                "type": "notes",
                "mode": "recent",
                "notes": [n.to_dict() for n in notes],
                "note_count": len(notes),
            }

    async def _render_search(self, spec: ViewSpec) -> dict[str, Any]:
        """Render search view across all providers."""
        query = spec.query or ""
        if not query:
            return {"error": "No search query provided", "results": []}

        results: list[dict[str, Any]] = []

        # Search notes
        if self.providers.has_notes():
            notes = await self.providers.notes.search(query, limit=5)
            for note in notes:
                preview = note.content[:100]
                if len(note.content) > 100:
                    preview += "..."
                results.append({
                    "type": "note",
                    "id": note.id,
                    "title": note.title,
                    "preview": preview,
                    "modified": note.modified.isoformat(),
                })

        # Search lists (search item text)
        if self.providers.has_lists():
            list_names = await self.providers.lists.get_lists()
            query_lower = query.lower()
            for list_name in list_names:
                items = await self.providers.lists.get_items(list_name, include_completed=True)
                for item in items:
                    if query_lower in item.text.lower():
                        results.append({
                            "type": "list_item",
                            "id": item.id,
                            "text": item.text,
                            "list": list_name,
                            "completed": item.completed,
                        })

        # Search calendar events
        if self.providers.has_calendar():
            now = datetime.now()
            events = await self.providers.calendar.get_events(
                now - timedelta(days=30),
                now + timedelta(days=90),
            )
            query_lower = query.lower()
            for event in events:
                if query_lower in event.title.lower() or (
                    event.notes and query_lower in event.notes.lower()
                ):
                    results.append({
                        "type": "event",
                        "id": event.id,
                        "title": event.title,
                        "start": event.start.isoformat(),
                        "end": event.end.isoformat(),
                    })

        return {
            "type": "search",
            "query": query,
            "results": results[:20],  # Limit results
            "result_count": len(results),
        }

    def _parse_date(self, value: str | None) -> datetime | None:
        """Parse a date string."""
        if not value:
            return None

        try:
            # Try ISO format first
            if "T" in value:
                return datetime.fromisoformat(value)
            else:
                return datetime.fromisoformat(value + "T00:00:00")
        except ValueError:
            pass

        # Try relative dates
        value_lower = value.lower()
        now = datetime.now()

        if value_lower == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif value_lower == "tomorrow":
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif value_lower == "yesterday":
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif "saturday" in value_lower:
            days_ahead = 5 - now.weekday()  # Saturday is 5
            if days_ahead <= 0:
                days_ahead += 7
            target = now + timedelta(days=days_ahead)
            return target.replace(hour=0, minute=0, second=0, microsecond=0)
        elif "sunday" in value_lower:
            days_ahead = 6 - now.weekday()  # Sunday is 6
            if days_ahead <= 0:
                days_ahead += 7
            target = now + timedelta(days=days_ahead)
            return target.replace(hour=0, minute=0, second=0, microsecond=0)

        return None

    # =========================================================================
    # NEW VIEW TYPES (RFC-078)
    # =========================================================================

    async def _render_table(self, spec: ViewSpec) -> dict[str, Any]:
        """Render table view from data source."""
        focus = spec.focus or {}
        data_source = focus.get("data_source", "list")
        columns = focus.get("columns")

        rows: list[dict[str, Any]] = []

        # Determine data source
        if data_source == "list" and self.providers.has_lists():
            list_name = focus.get("list_name", "default")
            items = await self.providers.lists.get_items(list_name, include_completed=True)
            rows = [i.to_dict() for i in items]
        elif data_source == "calendar" and self.providers.has_calendar():
            start = self._parse_date(focus.get("start")) or datetime.now()
            end = self._parse_date(focus.get("end")) or start + timedelta(days=30)
            events = await self.providers.calendar.get_events(start, end)
            rows = [e.to_dict() for e in events]
        elif data_source == "notes" and self.providers.has_notes():
            notes = await self.providers.notes.get_recent(limit=50)
            rows = [n.to_dict() for n in notes]
        elif data_source == "files" and self.providers.has_files():
            path = focus.get("path", ".")
            files = await self.providers.files.list_files(path, recursive=True)
            rows = [f.to_dict() for f in files[:100]]
        elif data_source == "projects" and self.providers.has_projects():
            projects = await self.providers.projects.list_projects()
            rows = [p.to_dict() for p in projects]

        # Infer columns from first row if not specified
        if rows and not columns:
            columns = list(rows[0].keys())

        return {
            "type": "table",
            "data_source": data_source,
            "rows": rows,
            "columns": columns or [],
            "row_count": len(rows),
        }

    async def _render_preview(self, spec: ViewSpec) -> dict[str, Any]:
        """Render file preview."""
        focus = spec.focus or {}
        file_path = focus.get("file_path") or focus.get("path")

        if not file_path:
            return {"error": "No file path specified", "type": "preview"}

        if not self.providers.has_files():
            return {"error": "Files provider not configured", "type": "preview"}

        # Get file metadata
        metadata = await self.providers.files.get_metadata(file_path)
        if not metadata:
            return {"error": f"File not found: {file_path}", "type": "preview"}

        # Determine content type from extension
        ext = metadata.extension or ""
        content_type = self._get_content_type(ext)

        result: dict[str, Any] = {
            "type": "preview",
            "file_path": file_path,
            "file_name": metadata.name,
            "content_type": content_type,
            "size": metadata.size,
            "modified": metadata.modified.isoformat(),
        }

        # For text-based content, include the actual content
        if content_type in ("markdown", "code", "text"):
            try:
                content = await self.providers.files.read_file(file_path)
                result["content"] = content
                if content_type == "code":
                    result["language"] = self._get_language(ext)
            except ValueError as e:
                result["error"] = str(e)

        return result

    async def _render_diff(self, spec: ViewSpec) -> dict[str, Any]:
        """Render diff between two files."""
        focus = spec.focus or {}
        left_path = focus.get("left_path")
        right_path = focus.get("right_path")

        if not left_path or not right_path:
            return {"error": "Both left_path and right_path required", "type": "diff"}

        if not self.providers.has_files():
            return {"error": "Files provider not configured", "type": "diff"}

        try:
            left_content = await self.providers.files.read_file(left_path)
            right_content = await self.providers.files.read_file(right_path)
        except (FileNotFoundError, ValueError) as e:
            return {"error": str(e), "type": "diff"}

        # Get metadata for both files
        left_meta = await self.providers.files.get_metadata(left_path)
        right_meta = await self.providers.files.get_metadata(right_path)

        return {
            "type": "diff",
            "left": {
                "path": left_path,
                "content": left_content,
                "name": left_meta.name if left_meta else Path(left_path).name,
            },
            "right": {
                "path": right_path,
                "content": right_content,
                "name": right_meta.name if right_meta else Path(right_path).name,
            },
        }

    async def _render_files(self, spec: ViewSpec) -> dict[str, Any]:
        """Render file listing."""
        if not self.providers.has_files():
            return {"error": "Files provider not configured", "files": []}

        focus = spec.focus or {}
        path = focus.get("path", ".")
        recursive = focus.get("recursive", False)

        files = await self.providers.files.list_files(path, recursive=recursive)

        return {
            "type": "files",
            "path": path,
            "recursive": recursive,
            "files": [f.to_dict() for f in files],
            "file_count": len(files),
            "dir_count": sum(1 for f in files if f.is_directory),
        }

    async def _render_projects(self, spec: ViewSpec) -> dict[str, Any]:
        """Render projects listing."""
        if not self.providers.has_projects():
            return {"error": "Projects provider not configured", "projects": []}

        focus = spec.focus or {}
        query = focus.get("query") or spec.query

        if query:
            projects = await self.providers.projects.search_projects(query)
        else:
            projects = await self.providers.projects.list_projects()

        return {
            "type": "projects",
            "query": query,
            "projects": [p.to_dict() for p in projects],
            "project_count": len(projects),
        }

    def _get_content_type(self, ext: str) -> str:
        """Determine content type from file extension."""
        ext_lower = ext.lower()

        if ext_lower in _MARKDOWN_EXTS:
            return "markdown"
        if ext_lower in _CODE_EXTS:
            return "code"
        if ext_lower in _IMAGE_EXTS:
            return "image"
        if ext_lower in _PDF_EXTS:
            return "pdf"
        return "text"

    def _get_language(self, ext: str) -> str:
        """Get programming language from file extension for syntax highlighting."""
        return _EXT_TO_LANGUAGE.get(ext.lower(), "text")

    # =========================================================================
    # GIT VIEW TYPES (RFC-078 Phase 2)
    # =========================================================================

    async def _render_git_status(self, spec: ViewSpec) -> dict[str, Any]:
        """Render git repository status."""
        if not self.providers.has_git():
            return {"error": "Git provider not configured", "type": "git_status"}

        focus = spec.focus or {}
        path = focus.get("path")

        status = await self.providers.git.get_status(path)

        return {
            "type": "git_status",
            "branch": status.branch,
            "ahead": status.ahead,
            "behind": status.behind,
            "is_clean": status.is_clean,
            "files": [f.to_dict() for f in status.files],
            "file_count": len(status.files),
            "staged_count": sum(1 for f in status.files if f.staged),
            "unstaged_count": sum(1 for f in status.files if not f.staged),
        }

    async def _render_git_log(self, spec: ViewSpec) -> dict[str, Any]:
        """Render git commit history."""
        if not self.providers.has_git():
            return {"error": "Git provider not configured", "type": "git_log"}

        focus = spec.focus or {}
        path = focus.get("path")
        limit = focus.get("limit", 50)

        commits = await self.providers.git.get_log(path, limit=limit)

        return {
            "type": "git_log",
            "commits": [c.to_dict() for c in commits],
            "commit_count": len(commits),
        }

    async def _render_git_branches(self, spec: ViewSpec) -> dict[str, Any]:
        """Render git branches."""
        if not self.providers.has_git():
            return {"error": "Git provider not configured", "type": "git_branches"}

        focus = spec.focus or {}
        path = focus.get("path")

        branches = await self.providers.git.get_branches(path)

        local_branches = [b for b in branches if not b.is_remote]
        remote_branches = [b for b in branches if b.is_remote]
        current_branch = next((b.name for b in branches if b.is_current), None)

        return {
            "type": "git_branches",
            "current": current_branch,
            "local": [b.to_dict() for b in local_branches],
            "remote": [b.to_dict() for b in remote_branches],
            "local_count": len(local_branches),
            "remote_count": len(remote_branches),
        }

    # =========================================================================
    # BOOKMARKS VIEW TYPE (RFC-078 Phase 2)
    # =========================================================================

    async def _render_bookmarks(self, spec: ViewSpec) -> dict[str, Any]:
        """Render bookmarks listing."""
        if not self.providers.has_bookmarks():
            return {"error": "Bookmarks provider not configured", "bookmarks": []}

        focus = spec.focus or {}
        query = focus.get("query") or spec.query
        tag = focus.get("tag")

        if tag:
            bookmarks = await self.providers.bookmarks.get_by_tag(tag)
        elif query:
            bookmarks = await self.providers.bookmarks.search(query)
        else:
            bookmarks = await self.providers.bookmarks.get_recent()

        # Get all tags for filter UI
        all_tags = await self.providers.bookmarks.get_all_tags()

        return {
            "type": "bookmarks",
            "query": query,
            "tag": tag,
            "bookmarks": [b.to_dict() for b in bookmarks],
            "bookmark_count": len(bookmarks),
            "all_tags": all_tags,
        }

    # =========================================================================
    # HABITS VIEW TYPE (RFC-078 Phase 4)
    # =========================================================================

    async def _render_habits(self, spec: ViewSpec) -> dict[str, Any]:
        """Render habits tracking overview."""
        if not self.providers.has_habits():
            return {"error": "Habits provider not configured", "habits": []}

        focus = spec.focus or {}
        include_archived = focus.get("include_archived", False)

        # Get all habits
        habits = await self.providers.habits.list_habits(include_archived=include_archived)

        # Get today's status for each habit
        habit_data: list[dict[str, Any]] = []
        for habit in habits:
            streak = await self.providers.habits.get_streak(habit.id)
            today_entries = await self.providers.habits.get_entries(
                habit.id,
                start=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            )
            completed_today = sum(e.count for e in today_entries)

            habit_data.append({
                **habit.to_dict(),
                "streak": streak,
                "completed_today": completed_today,
                "is_complete": completed_today >= habit.target_count,
            })

        # Calculate summary stats
        complete_count = sum(1 for h in habit_data if h["is_complete"])

        return {
            "type": "habits",
            "habits": habit_data,
            "habit_count": len(habits),
            "complete_count": complete_count,
            "incomplete_count": len(habits) - complete_count,
        }

    # =========================================================================
    # CONTACTS VIEW TYPE (RFC-078 Phase 4)
    # =========================================================================

    async def _render_contacts(self, spec: ViewSpec) -> dict[str, Any]:
        """Render contacts listing."""
        if not self.providers.has_contacts():
            return {"error": "Contacts provider not configured", "contacts": []}

        focus = spec.focus or {}
        query = focus.get("query") or spec.query
        tag = focus.get("tag")

        if tag:
            contacts = await self.providers.contacts.get_by_tag(tag)
        elif query:
            contacts = await self.providers.contacts.search(query)
        else:
            contacts = await self.providers.contacts.list_contacts()

        # Get all tags for filter UI
        all_tags = await self.providers.contacts.get_all_tags()

        return {
            "type": "contacts",
            "query": query,
            "tag": tag,
            "contacts": [c.to_dict() for c in contacts],
            "contact_count": len(contacts),
            "all_tags": all_tags,
        }
