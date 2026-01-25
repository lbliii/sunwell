"""Tests for Generative Interface (RFC-075)."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from sunwell.interface.core.types import ActionSpec, ViewSpec, IntentAnalysis
from sunwell.interface.executor import ActionExecutor, ActionResult
from sunwell.interface.views import ViewRenderer
from sunwell.interface.router import (
    InteractionRouter,
    ActionOutput,
    ViewOutput,
    ConversationOutput,
)
from sunwell.models.providers.registry import ProviderRegistry
from sunwell.models.providers.base import CalendarEvent


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def providers(temp_data_dir):
    """Create provider registry with temp directory."""
    return ProviderRegistry.create_default(temp_data_dir)


@pytest.fixture
def action_executor(providers):
    """Create action executor with providers."""
    return ActionExecutor(
        calendar=providers.calendar,
        lists=providers.lists,
    )


@pytest.fixture
def view_renderer(providers):
    """Create view renderer with providers."""
    return ViewRenderer(providers)


@pytest.fixture
def router(action_executor, view_renderer):
    """Create interaction router."""
    return InteractionRouter(
        action_executor=action_executor,
        view_renderer=view_renderer,
    )


class TestActionSpec:
    """Tests for ActionSpec type."""

    def test_to_dict(self):
        """ActionSpec serializes correctly."""
        action = ActionSpec(
            type="add_to_list",
            params={"list": "grocery", "item": "milk"},
        )
        result = action.to_dict()

        assert result["type"] == "add_to_list"
        assert result["params"]["list"] == "grocery"
        assert result["params"]["item"] == "milk"

    def test_from_dict(self):
        """ActionSpec deserializes correctly."""
        data = {"type": "add_to_list", "params": {"list": "grocery", "item": "milk"}}
        action = ActionSpec.from_dict(data)

        assert action.type == "add_to_list"
        assert action.params["list"] == "grocery"


class TestViewSpec:
    """Tests for ViewSpec type."""

    def test_calendar_view(self):
        """Calendar ViewSpec works correctly."""
        view = ViewSpec(
            type="calendar",
            focus={"start": "2026-01-20", "end": "2026-01-27"},
        )
        result = view.to_dict()

        assert result["type"] == "calendar"
        assert result["focus"]["start"] == "2026-01-20"


class TestIntentAnalysis:
    """Tests for IntentAnalysis type."""

    def test_action_intent(self):
        """Action intent analysis serializes correctly."""
        analysis = IntentAnalysis(
            interaction_type="action",
            confidence=0.95,
            action=ActionSpec(type="add_to_list", params={"list": "todo", "item": "test"}),
            response="Added test to your todo list.",
        )
        result = analysis.to_dict()

        assert result["interaction_type"] == "action"
        assert result["confidence"] == 0.95
        assert result["action"]["type"] == "add_to_list"
        assert result["response"] == "Added test to your todo list."


class TestActionExecutor:
    """Tests for ActionExecutor."""

    @pytest.mark.asyncio
    async def test_add_to_list(self, action_executor, providers):
        """Adding item to list succeeds."""
        action = ActionSpec(
            type="add_to_list",
            params={"list": "grocery", "item": "broccoli"},
        )
        result = await action_executor.execute(action)

        assert result.success
        assert "broccoli" in result.message

        # Verify item was added
        items = await providers.lists.get_items("grocery")
        assert any(i.text == "broccoli" for i in items)

    @pytest.mark.asyncio
    async def test_add_to_list_missing_item(self, action_executor):
        """Adding without item fails gracefully."""
        action = ActionSpec(type="add_to_list", params={"list": "grocery"})
        result = await action_executor.execute(action)

        assert not result.success
        assert "No item specified" in result.message

    @pytest.mark.asyncio
    async def test_create_event(self, action_executor, providers):
        """Creating calendar event succeeds."""
        action = ActionSpec(
            type="create_event",
            params={
                "title": "Test Meeting",
                "start": "tomorrow 3pm",
                "duration_minutes": 60,
            },
        )
        result = await action_executor.execute(action)

        assert result.success
        assert "Test Meeting" in result.message

    @pytest.mark.asyncio
    async def test_create_reminder(self, action_executor):
        """Creating reminder succeeds."""
        action = ActionSpec(
            type="create_reminder",
            params={"text": "Call mom", "when": "tomorrow"},
        )
        result = await action_executor.execute(action)

        assert result.success
        assert "Call mom" in result.message

    @pytest.mark.asyncio
    async def test_unknown_action(self, action_executor):
        """Unknown action type returns error."""
        action = ActionSpec(type="unknown_action", params={})
        result = await action_executor.execute(action)

        assert not result.success
        assert "Unknown action type" in result.message


class TestViewRenderer:
    """Tests for ViewRenderer."""

    @pytest.mark.asyncio
    async def test_calendar_view(self, view_renderer, providers):
        """Calendar view renders correctly."""
        # Add an event first
        now = datetime.now()
        event = CalendarEvent(
            id="",
            title="Test Event",
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2),
        )
        await providers.calendar.create_event(event)

        view = ViewSpec(type="calendar")
        result = await view_renderer.render(view)

        assert result["type"] == "calendar"
        assert result["event_count"] >= 1

    @pytest.mark.asyncio
    async def test_list_view(self, view_renderer, providers):
        """List view renders correctly."""
        # Add an item first
        await providers.lists.add_item("todo", "Test task")

        view = ViewSpec(type="list", focus={"list_name": "todo"})
        result = await view_renderer.render(view)

        assert result["type"] == "list"
        assert result["list_name"] == "todo"
        assert result["item_count"] >= 1

    @pytest.mark.asyncio
    async def test_notes_view_recent(self, view_renderer, providers):
        """Notes view shows recent notes."""
        # Create a note first
        await providers.notes.create("Test Note", "Test content")

        view = ViewSpec(type="notes", focus={"recent": True})
        result = await view_renderer.render(view)

        assert result["type"] == "notes"
        assert result["mode"] == "recent"
        assert result["note_count"] >= 1

    @pytest.mark.asyncio
    async def test_search_view(self, view_renderer, providers):
        """Search view finds items."""
        # Create searchable content
        await providers.notes.create("Searchable Note", "Contains special keyword")

        view = ViewSpec(type="search", query="special")
        result = await view_renderer.render(view)

        assert result["type"] == "search"
        assert result["query"] == "special"


class TestInteractionRouter:
    """Tests for InteractionRouter."""

    @pytest.mark.asyncio
    async def test_route_action(self, router, providers):
        """Action intent routes to action handler."""
        analysis = IntentAnalysis(
            interaction_type="action",
            confidence=0.9,
            action=ActionSpec(
                type="add_to_list",
                params={"list": "test", "item": "routed item"},
            ),
            response="Added routed item to test list.",
        )

        output = await router.route(analysis)

        assert isinstance(output, ActionOutput)
        assert output.success
        assert output.action_type == "add_to_list"

    @pytest.mark.asyncio
    async def test_route_view(self, router, providers):
        """View intent routes to view handler."""
        analysis = IntentAnalysis(
            interaction_type="view",
            confidence=0.9,
            view=ViewSpec(type="list", focus={"list_name": "test"}),
            response="Here's your test list.",
        )

        output = await router.route(analysis)

        assert isinstance(output, ViewOutput)
        assert output.view_type == "list"

    @pytest.mark.asyncio
    async def test_route_conversation(self, router):
        """Conversation intent routes to conversation handler."""
        analysis = IntentAnalysis(
            interaction_type="conversation",
            confidence=0.9,
            response="I understand you're feeling stressed.",
            conversation_mode="empathetic",
        )

        output = await router.route(analysis)

        assert isinstance(output, ConversationOutput)
        assert output.mode == "empathetic"
        assert "stressed" in output.response


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_create_default(self, temp_data_dir):
        """Default registry creates all providers."""
        registry = ProviderRegistry.create_default(temp_data_dir)

        assert registry.has_calendar()
        assert registry.has_lists()
        assert registry.has_notes()

    @pytest.mark.asyncio
    async def test_calendar_provider(self, providers):
        """Calendar provider works correctly."""
        now = datetime.now()
        event = CalendarEvent(
            id="",
            title="Test",
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2),
        )

        created = await providers.calendar.create_event(event)
        assert created.id != ""
        assert created.title == "Test"

        events = await providers.calendar.get_events(now, now + timedelta(days=1))
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_lists_provider(self, providers):
        """Lists provider works correctly."""
        item = await providers.lists.add_item("shopping", "Bread")
        assert item.text == "Bread"

        lists = await providers.lists.get_lists()
        assert "shopping" in lists

        items = await providers.lists.get_items("shopping")
        assert any(i.text == "Bread" for i in items)

    @pytest.mark.asyncio
    async def test_notes_provider(self, providers):
        """Notes provider works correctly."""
        note = await providers.notes.create("Test", "Content", ["tag1"])
        assert note.title == "Test"

        found = await providers.notes.search("Content")
        assert len(found) >= 1

        recent = await providers.notes.get_recent()
        assert len(recent) >= 1
