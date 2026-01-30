"""Slash command handling for the unified chat loop.

Handles /command parsing and execution.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.chat.state import LoopState

if TYPE_CHECKING:
    from sunwell.agent.background import BackgroundManager
    from sunwell.agent.rewind import SnapshotManager
    from sunwell.tools.execution import ToolExecutor

logger = logging.getLogger(__name__)


def handle_command(
    command: str,
    state: LoopState,
    tool_executor: ToolExecutor | None,
    conversation_history: list[dict[str, str]],
    request_cancel_fn: Callable[[], None],
    snapshot_manager: SnapshotManager | None = None,
) -> tuple[str | None, str | None]:
    """Handle /slash commands.

    Supports:
    - /agent [goal]: Force agent mode for explicit task (returns goal)
    - /chat: Stay in conversation mode
    - /abort: Cancel current execution
    - /status: Show current state
    - /tools on|off: Enable/disable tool execution
    - /rewind [mode|id]: Rewind code state

    Args:
        command: The command string (including /)
        state: Current loop state
        tool_executor: Tool executor instance or None
        conversation_history: Conversation history for status
        request_cancel_fn: Function to call for cancel requests
        snapshot_manager: SnapshotManager for rewind operations (optional)

    Returns:
        Tuple of (response_message, agent_goal). If agent_goal is set,
        caller should execute that goal. Otherwise, return response_message.
    """
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/agent" and arg:
        # Force agent mode - return the goal to execute
        return (None, arg)
    elif cmd == "/chat":
        return (
            "Staying in conversation mode. I won't execute tasks unless you use /agent.",
            None,
        )
    elif cmd == "/abort":
        is_executing = state in (LoopState.PLANNING, LoopState.EXECUTING)
        if is_executing:
            request_cancel_fn()
            return ("Cancellation requested...", None)
        return ("No execution in progress.", None)
    elif cmd == "/status":
        tools_status = "enabled" if tool_executor else "disabled"
        return (
            f"State: {state.value}, History: {len(conversation_history)} messages, "
            f"Tools: {tools_status}",
            None,
        )
    elif cmd == "/tools":
        # Return indicator that tools command needs special handling
        return (f"__TOOLS_COMMAND__:{arg}", None)
    elif cmd == "/rewind":
        # Return indicator that rewind command needs special handling
        return (f"__REWIND_COMMAND__:{arg}", None)
    elif cmd == "/background" or cmd == "/bg":
        # Return indicator that background command needs special handling
        return (f"__BACKGROUND_COMMAND__:{arg}", None)
    elif cmd == "/resume":
        # Return indicator that resume command needs special handling
        return (f"__RESUME_COMMAND__:{arg}", None)
    elif cmd == "/session":
        # Return indicator that session command needs special handling
        return (f"__SESSION_COMMAND__:{arg}", None)
    else:
        return (f"Unknown command: {cmd}", None)


def handle_rewind_command(
    arg: str,
    snapshot_manager: SnapshotManager | None,
    conversation_history: list[dict[str, str]],
) -> str:
    """Handle /rewind command for code state recovery.

    Supports:
    - /rewind          - Show recent snapshots
    - /rewind code     - Rewind files only, keep conversation
    - /rewind chat     - Rewind conversation only, keep files
    - /rewind both     - Rewind everything
    - /rewind <snap-id> - Rewind to specific snapshot

    Args:
        arg: Command argument (mode or snapshot ID)
        snapshot_manager: SnapshotManager instance
        conversation_history: Conversation history (mutable for chat rewind)

    Returns:
        Response message to display
    """
    from sunwell.agent.rewind import RewindMode

    if snapshot_manager is None:
        return "Rewind is not available (no snapshot manager)."

    arg_lower = arg.lower().strip()

    # No argument - show recent snapshots
    if not arg_lower:
        snapshots = snapshot_manager.list_snapshots(limit=10)
        if not snapshots:
            return "No snapshots available. Snapshots are created automatically before write operations."

        lines = ["**Recent Snapshots:**\n"]
        for snap in snapshots:
            stable_marker = " ★" if snap.is_stable else ""
            time_str = snap.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            label = f" - {snap.label}" if snap.label else ""
            lines.append(
                f"- `{snap.id}` ({time_str}) - {snap.file_count} files{label}{stable_marker}"
            )

        lines.append("\n**Usage:**")
        lines.append("- `/rewind code` - Rewind files only")
        lines.append("- `/rewind chat` - Clear conversation history")
        lines.append("- `/rewind both` - Rewind files and clear chat")
        lines.append("- `/rewind <snap-id>` - Rewind to specific snapshot")

        return "\n".join(lines)

    # Mode-based rewind (uses most recent snapshot)
    if arg_lower in ("code", "chat", "both"):
        snapshots = snapshot_manager.list_snapshots(limit=1)
        if not snapshots:
            return "No snapshots available to rewind to."

        latest = snapshots[0]

        if arg_lower == "code":
            result = snapshot_manager.rewind_to(latest.id, RewindMode.CODE_ONLY)
            if result.success:
                return (
                    f"✓ Rewound code to `{latest.id}`\n"
                    f"  - {result.files_restored} files restored\n"
                    f"  - {result.files_deleted} files deleted\n"
                    f"  - Conversation history preserved"
                )
            return f"✗ Rewind failed: {result.error}"

        elif arg_lower == "chat":
            # Clear conversation history
            history_len = len(conversation_history)
            conversation_history.clear()
            return f"✓ Cleared {history_len} messages from conversation history. Files unchanged."

        elif arg_lower == "both":
            result = snapshot_manager.rewind_to(latest.id, RewindMode.BOTH)
            history_len = len(conversation_history)
            conversation_history.clear()
            if result.success:
                return (
                    f"✓ Full rewind to `{latest.id}`\n"
                    f"  - {result.files_restored} files restored\n"
                    f"  - {result.files_deleted} files deleted\n"
                    f"  - {history_len} messages cleared"
                )
            return f"✗ Rewind failed: {result.error}"

    # Specific snapshot ID
    if arg_lower.startswith("snap-"):
        result = snapshot_manager.rewind_to(arg_lower, RewindMode.CODE_ONLY)
        if result.success:
            return (
                f"✓ Rewound to `{arg_lower}`\n"
                f"  - {result.files_restored} files restored\n"
                f"  - {result.files_deleted} files deleted"
            )
        return f"✗ Rewind failed: {result.error}"

    return (
        f"Unknown rewind option: `{arg}`\n\n"
        "Use `/rewind` to see available snapshots and options."
    )


def handle_background_command(
    arg: str,
    background_manager: BackgroundManager | None,
) -> str:
    """Handle /background command for viewing background sessions.

    Supports:
    - /background          - List background sessions
    - /background cancel <id> - Cancel a running session

    Args:
        arg: Command argument
        background_manager: BackgroundManager instance

    Returns:
        Response message to display
    """
    if background_manager is None:
        return "Background tasks are not available."

    arg_lower = arg.lower().strip()

    # No argument - list sessions
    if not arg_lower:
        sessions = background_manager.list_sessions(limit=10)
        if not sessions:
            return "No background sessions. Use long-running tasks to see them offered for background execution."

        lines = ["**Background Sessions:**\n"]
        for session in sessions:
            status_icon = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "⏹️",
                "pending": "⏳",
                "waiting": "⏸️",
            }.get(session.status.value, "❓")

            duration = ""
            if session.duration_seconds:
                mins = int(session.duration_seconds // 60)
                secs = int(session.duration_seconds % 60)
                if mins > 0:
                    duration = f" ({mins}m {secs}s)"
                else:
                    duration = f" ({secs}s)"

            lines.append(
                f"- {status_icon} `{session.session_id}` - {session.goal[:40]}...{duration}"
            )

            if session.status.value == "completed" and session.result_summary:
                lines.append(f"    → {session.result_summary}")
            elif session.status.value == "failed" and session.error:
                lines.append(f"    → Error: {session.error[:50]}")

        lines.append("\n**Commands:**")
        lines.append("- `/background cancel <id>` - Cancel a running session")

        return "\n".join(lines)

    # Cancel command
    if arg_lower.startswith("cancel "):
        session_id = arg_lower[7:].strip()
        if background_manager.cancel_session(session_id):
            return f"✓ Cancelled session `{session_id}`"
        return f"✗ Could not cancel `{session_id}` (not found or already complete)"

    return (
        f"Unknown background option: `{arg}`\n\n"
        "Use `/background` to see sessions and options."
    )


def handle_session_command(
    arg: str,
    loop: Any,  # UnifiedChatLoop
) -> str:
    """Handle /session command for session export/import.

    Supports:
    - /session export     - Export current session as token
    - /session import <token> - Import session from token
    - /session save <path>    - Save session to file
    - /session load <path>    - Load session from file

    Args:
        arg: Command argument
        loop: UnifiedChatLoop instance

    Returns:
        Response message to display
    """
    from sunwell.agent.session import PortableSession

    arg_parts = arg.strip().split(maxsplit=1)
    subcmd = arg_parts[0].lower() if arg_parts else ""
    subarg = arg_parts[1] if len(arg_parts) > 1 else ""

    # No argument - show help
    if not subcmd:
        return (
            "**Session Commands:**\n\n"
            "- `/session export` - Export session as shareable token\n"
            "- `/session import <token>` - Import session from token\n"
            "- `/session save <path>` - Save session to file\n"
            "- `/session load <path>` - Load session from file"
        )

    # Export
    if subcmd == "export":
        try:
            portable = PortableSession.from_chat_loop(loop)
            token = portable.to_token(expires_hours=24)

            return (
                f"**Session Exported**\n\n"
                f"Session ID: `{token.session_id}`\n"
                f"Messages: {len(portable.conversation_history)}\n"
                f"Expires: 24 hours\n\n"
                f"**Token:**\n```\n{token.token}\n```\n\n"
                f"Use `/session import <token>` to restore in another channel."
            )
        except Exception as e:
            return f"✗ Export failed: {e}"

    # Import
    if subcmd == "import":
        if not subarg:
            return "Usage: `/session import <token>`"

        try:
            portable = PortableSession.from_token(subarg.strip())
            portable.restore_to_chat_loop(loop)

            return (
                f"✓ Session imported: `{portable.session_id}`\n"
                f"Restored {len(portable.conversation_history)} messages"
            )
        except ValueError as e:
            return f"✗ Invalid token: {e}"
        except Exception as e:
            return f"✗ Import failed: {e}"

    # Save to file
    if subcmd == "save":
        if not subarg:
            return "Usage: `/session save <path>`"

        try:
            from pathlib import Path
            portable = PortableSession.from_chat_loop(loop)
            save_path = Path(subarg.strip()).expanduser()
            portable.save(save_path)

            return (
                f"✓ Session saved to `{save_path}`\n"
                f"Messages: {len(portable.conversation_history)}"
            )
        except Exception as e:
            return f"✗ Save failed: {e}"

    # Load from file
    if subcmd == "load":
        if not subarg:
            return "Usage: `/session load <path>`"

        try:
            from pathlib import Path
            load_path = Path(subarg.strip()).expanduser()
            
            if not load_path.exists():
                return f"✗ File not found: `{load_path}`"

            portable = PortableSession.load(load_path)
            portable.restore_to_chat_loop(loop)

            return (
                f"✓ Session loaded from `{load_path}`\n"
                f"Session ID: `{portable.session_id}`\n"
                f"Restored {len(portable.conversation_history)} messages"
            )
        except Exception as e:
            return f"✗ Load failed: {e}"

    return (
        f"Unknown session command: `{subcmd}`\n\n"
        "Use `/session` to see available commands."
    )


def handle_resume_command(
    arg: str,
    background_manager: BackgroundManager | None,
) -> str:
    """Handle /resume command for viewing background session results.

    Args:
        arg: Session ID to resume/inspect
        background_manager: BackgroundManager instance

    Returns:
        Response message with session details
    """
    if background_manager is None:
        return "Background tasks are not available."

    session_id = arg.strip()
    if not session_id:
        return "Usage: `/resume <session-id>`\n\nUse `/background` to see available sessions."

    session = background_manager.get_session(session_id)
    if session is None:
        return f"Session not found: `{session_id}`"

    lines = [f"**Session: {session_id}**\n"]
    lines.append(f"**Goal:** {session.goal}")
    lines.append(f"**Status:** {session.status.value}")

    if session.started_at:
        lines.append(f"**Started:** {session.started_at.strftime('%Y-%m-%d %H:%M:%S')}")

    if session.duration_seconds:
        mins = int(session.duration_seconds // 60)
        secs = int(session.duration_seconds % 60)
        if mins > 0:
            lines.append(f"**Duration:** {mins}m {secs}s")
        else:
            lines.append(f"**Duration:** {secs}s")

    if session.status.value == "completed":
        lines.append(f"\n**Result:** {session.result_summary}")
        lines.append(f"**Tasks Completed:** {session.tasks_completed}")
        if session.files_changed:
            lines.append(f"**Files Changed:** {', '.join(session.files_changed[:5])}")
            if len(session.files_changed) > 5:
                lines.append(f"  ... and {len(session.files_changed) - 5} more")

    elif session.status.value == "failed":
        lines.append(f"\n**Error:** {session.error}")

    return "\n".join(lines)


def handle_tools_command(
    arg: str,
    workspace: Path,
    trust_level: str,
    current_executor: ToolExecutor | None,
) -> tuple[str | None, ToolExecutor | None]:
    """Handle /tools on|off command to enable/disable tool execution.

    Args:
        arg: Command argument (on/off)
        workspace: Current workspace path
        trust_level: Trust level for tools
        current_executor: Current tool executor or None

    Returns:
        Tuple of (message, new_executor). new_executor is None if tools disabled,
        or a new ToolExecutor if enabled.
    """
    from sunwell.knowledge.project import (
        ProjectResolutionError,
        create_project_from_workspace,
        resolve_project,
    )
    from sunwell.tools.core.types import ToolPolicy, ToolTrust
    from sunwell.tools.execution import ToolExecutor

    arg_lower = arg.lower()
    if arg_lower == "on":
        if current_executor is not None:
            return ("Tools are already enabled.", current_executor)

        # Create tool executor
        try:
            project = resolve_project(cwd=workspace)
        except ProjectResolutionError:
            project = create_project_from_workspace(workspace)

        policy = ToolPolicy(trust_level=ToolTrust.from_string(trust_level))
        new_executor = ToolExecutor(
            project=project,
            sandbox=None,
            policy=policy,
        )
        logger.info("Tools enabled with trust_level=%s", trust_level)
        return ("✓ Tools enabled. I can now execute tasks.", new_executor)

    elif arg_lower == "off":
        if current_executor is None:
            return ("Tools are already disabled.", None)
        logger.info("Tools disabled")
        return ("✓ Tools disabled. I'll only respond to questions.", None)

    else:
        status = "enabled" if current_executor else "disabled"
        return (
            f"Tools are currently {status}. Use `/tools on` or `/tools off`.",
            current_executor,
        )
