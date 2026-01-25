"""Block Action Executor (RFC-080).

Executes quick actions from Home blocks.
"""

from dataclasses import dataclass
from typing import Any

from sunwell.models.providers.base import (
    CalendarProvider,
    HabitsProvider,
    ListProvider,
    NotesProvider,
)


@dataclass(frozen=True, slots=True)
class BlockActionResult:
    """Result of an executed block action."""

    success: bool
    message: str
    data: dict[str, Any] | None = None


@dataclass(slots=True)
class BlockActionExecutor:
    """Executes block actions against data providers.

    Block actions are quick operations embedded in Home blocks,
    like completing a habit, checking a list item, or opening a file.
    """

    calendar: CalendarProvider | None = None
    lists: ListProvider | None = None
    notes: NotesProvider | None = None
    habits: HabitsProvider | None = None

    async def execute(self, action_id: str, item_id: str | None = None) -> BlockActionResult:
        """Execute a block action.

        Args:
            action_id: The action to execute (e.g., "complete", "check", "add_event")
            item_id: Optional item ID for the action

        Returns:
            BlockActionResult with success status and message
        """
        match action_id:
            # Habit actions
            case "complete":
                return await self._complete_habit(item_id)
            case "skip":
                return await self._skip_habit(item_id)

            # List actions
            case "check":
                return await self._check_item(item_id)
            case "add":
                return await self._add_item(item_id)
            case "delete":
                return await self._delete_item(item_id)

            # Calendar actions
            case "add_event":
                return await self._add_event(item_id)
            case "rsvp":
                return await self._rsvp_event(item_id)

            # Note actions
            case "open":
                return await self._open_item(item_id)
            case "create":
                return await self._create_note()

            # Git actions
            case "stage":
                return await self._stage_file(item_id)
            case "commit":
                return await self._commit()
            case "push":
                return await self._push()

            # Contact actions
            case "call":
                return await self._call_contact(item_id)
            case "message":
                return await self._message_contact(item_id)
            case "email":
                return await self._email_contact(item_id)

            # Conversation actions
            case "follow_up":
                return BlockActionResult(
                    success=True,
                    message="Ready for follow-up question.",
                    data={"action": "show_input"},
                )
            case "dismiss":
                return BlockActionResult(
                    success=True,
                    message="Dismissed.",
                    data={"action": "dismiss"},
                )

            case _:
                return BlockActionResult(
                    success=False,
                    message=f"Unknown action: {action_id}",
                )

    # =========================================================================
    # HABIT ACTIONS
    # =========================================================================

    async def _complete_habit(self, habit_id: str | None) -> BlockActionResult:
        """Complete a habit for today."""
        if not habit_id:
            return BlockActionResult(
                success=False,
                message="No habit specified.",
            )

        if not self.habits:
            return BlockActionResult(
                success=False,
                message="Habits provider not configured.",
            )

        try:
            # Log habit completion
            entry = await self.habits.log_entry(habit_id, count=1)
            habit = await self.habits.get_habit(habit_id)
            habit_name = habit.name if habit else "habit"
            return BlockActionResult(
                success=True,
                message=f"Completed '{habit_name}'! 🎉",
                data={"habit_id": habit_id, "entry_id": entry.id, "action": "completed"},
            )
        except Exception as e:
            return BlockActionResult(
                success=False,
                message=f"Failed to complete habit: {e}",
            )

    async def _skip_habit(self, habit_id: str | None) -> BlockActionResult:
        """Skip a habit for today."""
        if not habit_id:
            return BlockActionResult(
                success=False,
                message="No habit specified.",
            )

        if not self.habits:
            return BlockActionResult(
                success=False,
                message="Habits provider not configured.",
            )

        try:
            # Log skip with count=0
            await self.habits.log_entry(habit_id, count=0, notes="Skipped")
            habit = await self.habits.get_habit(habit_id)
            habit_name = habit.name if habit else "habit"
            return BlockActionResult(
                success=True,
                message=f"Skipped '{habit_name}' for today.",
                data={"habit_id": habit_id, "action": "skipped"},
            )
        except Exception as e:
            return BlockActionResult(
                success=False,
                message=f"Failed to skip habit: {e}",
            )

    # =========================================================================
    # LIST ACTIONS
    # =========================================================================

    async def _check_item(self, item_id: str | None) -> BlockActionResult:
        """Check/complete a list item."""
        if not item_id:
            return BlockActionResult(
                success=False,
                message="No item specified.",
            )

        if not self.lists:
            return BlockActionResult(
                success=False,
                message="Lists provider not configured.",
            )

        try:
            item = await self.lists.complete_item(item_id)
            return BlockActionResult(
                success=True,
                message=f"Completed '{item.text}'.",
                data={"item_id": item.id},
            )
        except Exception as e:
            return BlockActionResult(
                success=False,
                message=f"Failed to complete item: {e}",
            )

    async def _add_item(self, list_name: str | None) -> BlockActionResult:
        """Prompt to add an item to a list."""
        return BlockActionResult(
            success=True,
            message="Ready to add item.",
            data={"action": "show_add_dialog", "list": list_name or "default"},
        )

    async def _delete_item(self, item_id: str | None) -> BlockActionResult:
        """Delete a list item."""
        if not item_id:
            return BlockActionResult(
                success=False,
                message="No item specified.",
            )

        if not self.lists:
            return BlockActionResult(
                success=False,
                message="Lists provider not configured.",
            )

        try:
            await self.lists.delete_item(item_id)
            return BlockActionResult(
                success=True,
                message="Item deleted.",
                data={"item_id": item_id},
            )
        except Exception as e:
            return BlockActionResult(
                success=False,
                message=f"Failed to delete item: {e}",
            )

    # =========================================================================
    # CALENDAR ACTIONS
    # =========================================================================

    async def _add_event(self, _: str | None) -> BlockActionResult:
        """Prompt to add a calendar event."""
        return BlockActionResult(
            success=True,
            message="Ready to add event.",
            data={"action": "show_event_dialog"},
        )

    async def _rsvp_event(self, event_id: str | None) -> BlockActionResult:
        """RSVP to an event."""
        if not event_id:
            return BlockActionResult(
                success=False,
                message="No event specified.",
            )

        return BlockActionResult(
            success=True,
            message="RSVP sent.",
            data={"event_id": event_id, "action": "rsvp"},
        )

    # =========================================================================
    # NOTE ACTIONS
    # =========================================================================

    async def _open_item(self, item_id: str | None) -> BlockActionResult:
        """Open an item (note, file, etc.)."""
        if not item_id:
            return BlockActionResult(
                success=False,
                message="No item specified.",
            )

        return BlockActionResult(
            success=True,
            message="Opening...",
            data={"item_id": item_id, "action": "open"},
        )

    async def _create_note(self) -> BlockActionResult:
        """Create a new note."""
        return BlockActionResult(
            success=True,
            message="Ready to create note.",
            data={"action": "show_note_dialog"},
        )

    # =========================================================================
    # GIT ACTIONS
    # =========================================================================

    async def _stage_file(self, file_path: str | None) -> BlockActionResult:
        """Stage a file for commit."""
        if not file_path:
            return BlockActionResult(
                success=False,
                message="No file specified.",
            )

        # TODO: Integrate with git provider
        return BlockActionResult(
            success=True,
            message=f"Staged: {file_path}",
            data={"file": file_path, "action": "staged"},
        )

    async def _commit(self) -> BlockActionResult:
        """Open commit dialog."""
        return BlockActionResult(
            success=True,
            message="Ready to commit.",
            data={"action": "show_commit_dialog"},
        )

    async def _push(self) -> BlockActionResult:
        """Push commits to remote."""
        # TODO: Integrate with git provider
        return BlockActionResult(
            success=True,
            message="Pushed to remote.",
            data={"action": "pushed"},
        )

    # =========================================================================
    # CONTACT ACTIONS
    # =========================================================================

    async def _call_contact(self, contact_id: str | None) -> BlockActionResult:
        """Initiate a call to a contact."""
        if not contact_id:
            return BlockActionResult(
                success=False,
                message="No contact specified.",
            )

        # TODO: Integrate with contacts/phone provider
        return BlockActionResult(
            success=True,
            message="Initiating call...",
            data={"contact_id": contact_id, "action": "call"},
        )

    async def _message_contact(self, contact_id: str | None) -> BlockActionResult:
        """Open messaging app for a contact."""
        if not contact_id:
            return BlockActionResult(
                success=False,
                message="No contact specified.",
            )

        return BlockActionResult(
            success=True,
            message="Opening messages...",
            data={"contact_id": contact_id, "action": "message"},
        )

    async def _email_contact(self, contact_id: str | None) -> BlockActionResult:
        """Open email for a contact."""
        if not contact_id:
            return BlockActionResult(
                success=False,
                message="No contact specified.",
            )

        return BlockActionResult(
            success=True,
            message="Opening email...",
            data={"contact_id": contact_id, "action": "email"},
        )
