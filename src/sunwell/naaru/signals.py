"""Signal handling for graceful interruption in the Naaru architecture."""

from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class StopReason(Enum):
    """Reason for stopping the autonomous loop."""

    USER_INTERRUPT = "user_interrupt"      # Ctrl+C or SIGTERM
    STOP_COMMAND = "stop_command"          # sunwell autonomous stop
    TIME_LIMIT = "time_limit"              # Max hours reached
    PROPOSAL_LIMIT = "proposal_limit"      # Max proposals reached
    FAILURE_LIMIT = "failure_limit"        # Too many consecutive failures
    IDLE = "idle"                          # No more work to do
    ERROR = "error"                        # Unrecoverable error
    COMPLETED = "completed"                # All opportunities processed


@dataclass
class SignalHandler:
    """Handle interruption signals for graceful shutdown.

    Supports multiple interruption methods:
    - Ctrl+C (SIGINT)
    - SIGTERM (kill signal)
    - Stop file (sunwell autonomous stop)
    - Programmatic stop

    All methods result in graceful shutdown:
    1. Current task completes
    2. State is checkpointed
    3. Summary is displayed
    """

    session_id: str
    storage_path: Path
    on_stop: Callable[[StopReason], None] | None = None

    _stop_requested: bool = field(default=False, init=False)
    _stop_reason: StopReason | None = field(default=None, init=False)
    _original_sigint: signal.Handlers | None = field(default=None, init=False)
    _original_sigterm: signal.Handlers | None = field(default=None, init=False)
    _check_task: asyncio.Task | None = field(default=None, init=False)

    def setup(self) -> None:
        """Setup signal handlers."""
        # Save original handlers
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        # Install our handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # Create stop file marker (delete any existing)
        self._stop_file.unlink(missing_ok=True)

    def teardown(self) -> None:
        """Restore original signal handlers."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)

        # Clean up stop file
        self._stop_file.unlink(missing_ok=True)

        # Cancel check task
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()

    @property
    def _stop_file(self) -> Path:
        """Path to the stop signal file."""
        return self.storage_path / f"{self.session_id}.stop"

    def _handle_signal(self, signum: int, frame) -> None:
        """Handle SIGINT or SIGTERM."""
        self._request_stop(StopReason.USER_INTERRUPT)
        print("\n⏸️  Received signal, stopping gracefully...")
        print("   (Press Ctrl+C again to force quit)")

        # On second Ctrl+C, exit immediately
        signal.signal(signal.SIGINT, self._force_quit)

    def _force_quit(self, signum: int, frame) -> None:
        """Force quit on second interrupt."""
        print("\n❌ Force quit!")
        sys.exit(1)

    def _request_stop(self, reason: StopReason) -> None:
        """Request a graceful stop."""
        if not self._stop_requested:
            self._stop_requested = True
            self._stop_reason = reason

            if self.on_stop:
                self.on_stop(reason)

    def request_stop(self, reason: StopReason = StopReason.STOP_COMMAND) -> None:
        """Programmatically request a stop."""
        self._request_stop(reason)

    def create_stop_file(self) -> None:
        """Create stop file (for external stop command)."""
        self._stop_file.parent.mkdir(parents=True, exist_ok=True)
        self._stop_file.write_text(datetime.now().isoformat())

    @property
    def stop_requested(self) -> bool:
        """Check if stop has been requested."""
        # Check stop file
        if not self._stop_requested and self._stop_file.exists():
            self._request_stop(StopReason.STOP_COMMAND)

        return self._stop_requested

    @property
    def stop_reason(self) -> StopReason | None:
        """Get the reason for stopping."""
        return self._stop_reason

    async def start_file_watcher(self) -> None:
        """Start watching for stop file (async)."""
        async def watch():
            while not self._stop_requested:
                if self._stop_file.exists():
                    self._request_stop(StopReason.STOP_COMMAND)
                    break
                await asyncio.sleep(1)

        self._check_task = asyncio.create_task(watch())

    def check_limits(
        self,
        runtime_seconds: float,
        max_hours: float,
        proposals_created: int,
        max_proposals: int,
        consecutive_failures: int,
        max_failures: int,
    ) -> bool:
        """Check if any limits have been reached.

        Returns True if should stop.
        """
        if runtime_seconds >= max_hours * 3600:
            self._request_stop(StopReason.TIME_LIMIT)
            return True

        if proposals_created >= max_proposals:
            self._request_stop(StopReason.PROPOSAL_LIMIT)
            return True

        if consecutive_failures >= max_failures:
            self._request_stop(StopReason.FAILURE_LIMIT)
            return True

        return False


def format_stop_reason(reason: StopReason) -> str:
    """Get human-readable description of stop reason."""
    descriptions = {
        StopReason.USER_INTERRUPT: "User interrupted (Ctrl+C)",
        StopReason.STOP_COMMAND: "Stop command received",
        StopReason.TIME_LIMIT: "Maximum runtime reached",
        StopReason.PROPOSAL_LIMIT: "Maximum proposals created",
        StopReason.FAILURE_LIMIT: "Too many consecutive failures",
        StopReason.IDLE: "No more work to do",
        StopReason.ERROR: "Unrecoverable error occurred",
        StopReason.COMPLETED: "All opportunities processed",
    }
    return descriptions.get(reason, str(reason))
