"""Main control loop for the Naaru architecture.

Sessions are persisted globally at ~/.sunwell/sessions/ for cross-project
session management and resume capability.
"""


import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sunwell.features.mirror import MirrorHandler
from sunwell.planning.naaru.discovery import OpportunityDiscoverer
from sunwell.planning.naaru.session_store import SessionStore
from sunwell.planning.naaru.signals import SignalHandler, StopReason, format_stop_reason
from sunwell.planning.naaru.types import (
    CompletedTask,
    Opportunity,
    SessionConfig,
    SessionState,
    SessionStatus,
)


@dataclass(slots=True)
class AutonomousRunner:
    """Main runner for autonomous mode.

    Executes the autonomous control loop:
    1. Discover improvement opportunities
    2. Prioritize by goal alignment
    3. Work on each opportunity
    4. Checkpoint progress
    5. Repeat until stopped or limits reached

    Example:
        >>> config = SessionConfig(goals=["improve error handling"])
        >>> runner = AutonomousRunner(config, workspace=Path("."))
        >>> await runner.start()
    """

    config: SessionConfig
    workspace: Path
    storage_path: Path = None
    on_event: Callable[[str, str], None] | None = None
    project_id: str | None = None
    workspace_id: str | None = None

    # Internal state
    state: SessionState = field(init=False)
    mirror: MirrorHandler = field(init=False)
    discoverer: OpportunityDiscoverer = field(init=False)
    signals: SignalHandler = field(init=False)
    _session_store: SessionStore = field(init=False)
    _loop_start: datetime = field(init=False)

    def __post_init__(self):
        """Initialize components."""
        # Use global session store for persistence
        self._session_store = SessionStore()

        # Legacy storage path for local artifacts (mirror, signals)
        if self.storage_path is None:
            self.storage_path = self.workspace / ".sunwell" / "autonomous"

        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def start(self) -> SessionState:
        """Start the autonomous loop.

        Returns:
            Final session state
        """
        # Initialize session
        self.state = SessionState(
            session_id=f"auto_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
            config=self.config,
            status=SessionStatus.RUNNING,
            started_at=datetime.now(),
        )

        # Save initial state to global store
        self._session_store.save(self.state)

        # Set metadata for project/workspace association
        if self.project_id or self.workspace_id:
            self._session_store.set_metadata(
                self.state.session_id,
                project_id=self.project_id,
                workspace_id=self.workspace_id,
            )

        # Initialize mirror handler
        self.mirror = MirrorHandler(
            workspace=self.workspace,
            storage_path=self.storage_path / "mirror",
        )

        # Initialize discoverer
        self.discoverer = OpportunityDiscoverer(
            mirror=self.mirror,
            workspace=self.workspace,
        )

        # Setup signal handling
        self.signals = SignalHandler(
            session_id=self.state.session_id,
            storage_path=self.storage_path,
            on_stop=lambda r: self._emit("stop_signal", format_stop_reason(r)),
        )
        self.signals.setup()

        try:
            # Start file watcher for stop command
            await self.signals.start_file_watcher()

            # Display startup banner
            self._display_banner()

            # Run the main loop
            self._loop_start = datetime.now()
            await self._run_loop()

        except Exception as e:
            self.state.status = SessionStatus.FAILED
            self.state.stop_reason = str(e)
            self._emit("error", f"Fatal error: {e}")
        finally:
            # Cleanup
            self.signals.teardown()
            await self._finalize()

        return self.state

    @classmethod
    async def resume(
        cls,
        session_id: str,
        workspace: Path,
        on_event: Callable[[str, str], None] | None = None,
    ) -> SessionState:
        """Resume a paused or interrupted session.

        Args:
            session_id: Session to resume.
            workspace: Workspace path for local operations.
            on_event: Optional event callback.

        Returns:
            Final session state.

        Raises:
            ValueError: If session not found or not resumable.
        """
        store = SessionStore()
        state = store.load(session_id)

        if not state:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)

        if state.status not in (SessionStatus.PAUSED, SessionStatus.RUNNING):
            msg = f"Session cannot be resumed (status: {state.status.value})"
            raise ValueError(msg)

        # Create runner with restored state
        runner = cls(
            config=state.config,
            workspace=workspace,
            on_event=on_event,
        )
        runner.state = state
        runner.state.status = SessionStatus.RUNNING
        runner._session_store = store

        # Initialize components
        runner.storage_path = workspace / ".sunwell" / "autonomous"
        runner.storage_path.mkdir(parents=True, exist_ok=True)

        runner.mirror = MirrorHandler(
            workspace=workspace,
            storage_path=runner.storage_path / "mirror",
        )

        runner.discoverer = OpportunityDiscoverer(
            mirror=runner.mirror,
            workspace=workspace,
        )

        runner.signals = SignalHandler(
            session_id=state.session_id,
            storage_path=runner.storage_path,
            on_stop=lambda r: runner._emit("stop_signal", format_stop_reason(r)),
        )
        runner.signals.setup()

        try:
            await runner.signals.start_file_watcher()
            runner._emit("resume", f"Resuming session {session_id}")

            runner._loop_start = datetime.now()
            await runner._run_loop()

        except Exception as e:
            runner.state.status = SessionStatus.FAILED
            runner.state.stop_reason = str(e)
            runner._emit("error", f"Fatal error: {e}")
        finally:
            runner.signals.teardown()
            await runner._finalize()

        return runner.state

    async def _run_loop(self) -> None:
        """Main execution loop."""
        # Discovery phase
        self._emit("phase", "Discovery - Scanning for opportunities...")
        self.state.opportunities = await self.discoverer.discover(self.config.goals)

        if not self.state.opportunities:
            self._emit("idle", "No opportunities found")
            self.signals.request_stop(StopReason.IDLE)
            return

        self._emit(
            "discovery_complete",
            f"Found {len(self.state.opportunities)} opportunities",
        )

        # Display top opportunities
        self._display_opportunities()

        # Work loop
        while not self._should_stop():
            # Update runtime
            self.state.total_runtime_seconds = (
                datetime.now() - self._loop_start
            ).total_seconds()

            # Work on next opportunity
            if self.state.opportunities:
                await self._work_on_next()
            else:
                self.signals.request_stop(StopReason.COMPLETED)
                break

            # Checkpoint
            await self._checkpoint()

            # Cooldown between changes
            await asyncio.sleep(self.config.min_seconds_between_changes)

    async def _work_on_next(self) -> None:
        """Work on the next highest priority opportunity."""
        opp = self.state.opportunities.pop(0)
        self.state.current_task = opp

        self._emit("work_start", f"Starting: {opp.description}")

        result = "failed"
        proposal_id = None

        try:
            # Map category to proposal scope
            scope_map = {
                "error_handling": "validator",
                "testing": "validator",
                "performance": "workflow",
                "documentation": "heuristic",
                "code_quality": "heuristic",
                "security": "validator",
                "other": "heuristic",
            }
            scope = scope_map.get(opp.category.value, "heuristic")

            # Generate proposal using mirror neurons
            proposal_result = await self.mirror.handle("propose_improvement", {
                "scope": scope,
                "problem": opp.description,
                "evidence": [
                    f"Target: {opp.target_module}",
                    f"Priority: {opp.priority:.2f}",
                    f"Details: {json.dumps(opp.details)}",
                ],
                "diff": f"# Improvement for: {opp.description}\n# Auto-generated by autonomous mode",
            })

            proposal_data = json.loads(proposal_result)

            if "error" in proposal_data:
                self._emit("rejected", f"Safety check failed: {proposal_data['error']}")
                self.state.proposals_rejected += 1
                result = "rejected"
            else:
                proposal_id = proposal_data.get("proposal_id")
                self.state.proposals_created += 1
                self._emit("proposal_created", f"Created {proposal_id}")

                # Decide: auto-apply or queue
                if self._can_auto_apply(opp):
                    # Submit and approve
                    await self.mirror.handle("submit_proposal", {"proposal_id": proposal_id})

                    # For demo purposes, we'll approve it
                    from sunwell.features.mirror.proposals import ProposalManager
                    manager = ProposalManager(self.storage_path / "mirror" / "proposals")
                    manager.approve_proposal(proposal_id)

                    # Apply
                    apply_result = await self.mirror.handle("apply_proposal", {
                        "proposal_id": proposal_id,
                    })
                    apply_data = json.loads(apply_result)

                    if "error" not in apply_data:
                        self.state.proposals_auto_applied += 1
                        result = "auto_applied"
                        self._emit("auto_applied", f"Auto-applied {proposal_id}")
                    else:
                        self.state.proposals_queued += 1
                        result = "queued"
                        self._emit("queued", f"Failed to apply, queued: {proposal_id}")
                else:
                    # Just submit for review
                    await self.mirror.handle("submit_proposal", {"proposal_id": proposal_id})
                    self.state.proposals_queued += 1
                    result = "queued"
                    self._emit("queued", f"Queued for review: {proposal_id}")

                self.state.consecutive_failures = 0

        except Exception as e:
            self._emit("error", f"Failed: {e}")
            self.state.consecutive_failures += 1
            result = "failed"

        # Record completion
        self.state.completed.append(CompletedTask(
            opportunity_id=opp.id,
            proposal_id=proposal_id,
            result=result,
            timestamp=datetime.now(),
        ))

        self.state.current_task = None

    def _can_auto_apply(self, opp: Opportunity) -> bool:
        """Check if an opportunity can be auto-applied."""
        if not self.config.auto_apply_enabled:
            return False

        if self.state.proposals_auto_applied >= self.config.max_auto_apply:
            return False

        return opp.risk_level.can_auto_apply()

    def _should_stop(self) -> bool:
        """Check if the loop should stop."""
        # Check signal handler
        if self.signals.stop_requested:
            return True

        # Check limits
        return self.signals.check_limits(
            runtime_seconds=self.state.total_runtime_seconds,
            max_hours=self.config.max_hours,
            proposals_created=self.state.proposals_created,
            max_proposals=self.config.max_proposals,
            consecutive_failures=self.state.consecutive_failures,
            max_failures=self.config.max_consecutive_failures,
        )

    async def _checkpoint(self) -> None:
        """Save current state to global store and local checkpoint."""
        self.state.checkpoint_at = datetime.now()

        # Save to global session store
        self._session_store.save(self.state)

        # Also save local checkpoint for legacy compatibility
        checkpoint_path = self.storage_path / f"{self.state.session_id}.json"
        self.state.save(checkpoint_path)

        if self.config.verbose:
            self._emit("checkpoint", "Saved checkpoint")

    async def _finalize(self) -> None:
        """Finalize the session."""
        self.state.stopped_at = datetime.now()
        self.state.stop_reason = format_stop_reason(
            self.signals.stop_reason or StopReason.COMPLETED
        )

        if self.state.status == SessionStatus.RUNNING:
            if self.signals.stop_reason in [StopReason.COMPLETED, StopReason.IDLE]:
                self.state.status = SessionStatus.COMPLETED
            else:
                self.state.status = SessionStatus.PAUSED

        # Final save to global store
        self._session_store.save(self.state)

        # Also save local checkpoint for legacy compatibility
        checkpoint_path = self.storage_path / f"{self.state.session_id}.json"
        self.state.save(checkpoint_path)

        # Display summary
        self._display_summary()

    def _emit(self, event: str, message: str) -> None:
        """Emit a progress event."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Map events to emojis
        emojis = {
            "phase": "📋",
            "discovery_complete": "📊",
            "work_start": "🔧",
            "proposal_created": "💡",
            "auto_applied": "✅",
            "queued": "📝",
            "rejected": "❌",
            "error": "⚠️",
            "checkpoint": "💾",
            "idle": "😴",
            "stop_signal": "⏸️",
        }

        emoji = emojis.get(event, "•")
        print(f"[{timestamp}] {emoji} {message}")

        if self.on_event:
            self.on_event(event, message)

    def _display_banner(self) -> None:
        """Display startup banner."""
        print()
        print("╔" + "═" * 78 + "╗")
        print("║" + " 🤖 AUTONOMOUS MODE STARTED".ljust(78) + "║")
        print("╠" + "═" * 78 + "╣")
        print(f"║  Session:     {self.state.session_id}".ljust(79) + "║")
        print(f"║  Goals:       {', '.join(self.config.goals)[:60]}".ljust(79) + "║")
        print(f"║  Max Runtime: {self.config.max_hours} hours".ljust(79) + "║")
        print(f"║  Auto-Apply:  {'enabled (low-risk only)' if self.config.auto_apply_enabled else 'disabled'}".ljust(79) + "║")
        print("║" + " " * 78 + "║")
        print("║  Controls:".ljust(79) + "║")
        print("║    • Ctrl+C           - Graceful stop".ljust(79) + "║")
        print("║    • sunwell auto stop - Stop from another terminal".ljust(79) + "║")
        print("╚" + "═" * 78 + "╝")
        print()

    def _display_opportunities(self) -> None:
        """Display top opportunities."""
        print()
        print(f"📋 Top {min(5, len(self.state.opportunities))} Opportunities:")
        for i, opp in enumerate(self.state.opportunities[:5], 1):
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
                opp.risk_level.value, "⚪"
            )
            print(f"   {i}. [{opp.priority:.2f}] {risk_emoji} {opp.description}")
        print()

    def _display_summary(self) -> None:
        """Display session summary."""
        progress = self.state.get_progress_summary()
        runtime = timedelta(seconds=int(self.state.total_runtime_seconds))

        print()
        print("╔" + "═" * 78 + "╗")
        print("║" + " 📊 SESSION SUMMARY".ljust(78) + "║")
        print("╠" + "═" * 78 + "╣")
        print(f"║  Runtime:           {runtime}".ljust(79) + "║")
        print(f"║  Status:            {self.state.status.value}".ljust(79) + "║")
        print(f"║  Stop Reason:       {self.state.stop_reason or 'N/A'}".ljust(79) + "║")
        print("║" + " " * 78 + "║")
        print(f"║  Opportunities:     {progress['opportunities_completed']}/{progress['opportunities_total']} completed".ljust(79) + "║")
        print(f"║  Proposals Created: {progress['proposals_created']}".ljust(79) + "║")
        print(f"║    • Auto-applied:  {progress['proposals_auto_applied']}".ljust(79) + "║")
        print(f"║    • Queued:        {progress['proposals_queued']}".ljust(79) + "║")
        print(f"║    • Rejected:      {progress['proposals_rejected']}".ljust(79) + "║")
        print("║" + " " * 78 + "║")
        print("║  Next Steps:".ljust(79) + "║")

        if progress['proposals_queued'] > 0:
            print("║    • Review queued proposals".ljust(79) + "║")
        if self.state.status == SessionStatus.PAUSED:
            print(f"║    • Resume: sunwell autonomous resume {self.state.session_id}".ljust(79) + "║")

        print("╚" + "═" * 78 + "╝")
        print()


async def resume_session(
    session_path: Path,
    workspace: Path,
) -> SessionState:
    """Resume a paused session.

    Args:
        session_path: Path to the session JSON file
        workspace: User's workspace directory

    Returns:
        Final session state
    """
    # Load state
    state = SessionState.load(session_path)

    if state.status not in [SessionStatus.PAUSED, SessionStatus.RUNNING]:
        raise ValueError(f"Cannot resume session with status: {state.status.value}")

    # Create runner with existing config
    runner = AutonomousRunner(
        config=state.config,
        workspace=workspace,
        storage_path=session_path.parent,
    )

    # Restore state
    runner.state = state
    runner.state.status = SessionStatus.RUNNING

    # Continue from where we left off
    # ... (simplified - full implementation would restore opportunities, etc.)

    return await runner.start()
