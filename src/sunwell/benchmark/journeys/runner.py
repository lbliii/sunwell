"""JourneyRunner for executing behavioral test journeys.

Orchestrates journey execution:
1. Sets up workspace with files
2. Runs agent with EventRecorder capturing events
3. Checks behavioral assertions
4. Returns structured results
"""

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import Any

from rich.console import Console
from rich.panel import Panel

from sunwell.benchmark.journeys.assertions import AssertionReport, BehavioralAssertions
from sunwell.benchmark.journeys.recorder import EventRecorder
from sunwell.benchmark.journeys.types import (
    Journey,
    JourneyType,
    MultiTurnJourney,
    Setup,
    SingleTurnJourney,
    Turn,
)

logger = logging.getLogger(__name__)

# Verbose console for debug output
_verbose_console = Console()


@dataclass(slots=True)
class TurnResult:
    """Result of a single turn in a journey."""

    turn_index: int
    """Which turn (0-indexed)."""

    input: str
    """User input for this turn."""

    passed: bool
    """Whether all assertions passed."""

    assertion_report: AssertionReport
    """Detailed assertion results."""

    duration_ms: int
    """Time taken for this turn."""

    output: str = ""
    """Model output/response."""

    error: str | None = None
    """Error message if failed."""


@dataclass(slots=True)
class JourneyResult:
    """Result of running a complete journey."""

    journey_id: str
    """Journey identifier."""

    passed: bool
    """Whether the journey passed (all assertions)."""

    turn_results: list[TurnResult] = field(default_factory=list)
    """Results for each turn."""

    assertion_report: AssertionReport = field(default_factory=AssertionReport)
    """Combined assertion report."""

    events: list[Any] = field(default_factory=list)
    """All captured events."""

    duration_ms: int = 0
    """Total execution time."""

    error: str | None = None
    """Error if journey failed to run."""

    retry_count: int = 0
    """Number of retries attempted."""

    workspace: str = ""
    """Workspace path used."""

    @property
    def intent_match(self) -> bool:
        """Whether intent assertions passed."""
        return all(
            r.passed for r in self.assertion_report.results
            if r.category == "intent"
        )

    @property
    def signals_match(self) -> bool:
        """Whether signal assertions passed."""
        return all(
            r.passed for r in self.assertion_report.results
            if r.category == "signals"
        )

    @property
    def tools_match(self) -> bool:
        """Whether tool assertions passed."""
        return all(
            r.passed for r in self.assertion_report.results
            if r.category == "tools"
        )

    @property
    def state_match(self) -> bool:
        """Whether file/state assertions passed."""
        return all(
            r.passed for r in self.assertion_report.results
            if r.category == "files"
        )

    @property
    def output_match(self) -> bool:
        """Whether output assertions passed."""
        return all(
            r.passed for r in self.assertion_report.results
            if r.category == "output"
        )


class JourneyRunner:
    """Execute journeys and collect behavioral assertions.

    Usage:
        >>> runner = JourneyRunner()
        >>> result = await runner.run(journey)
        >>> assert result.passed

    Supports:
    - Single-turn journeys (one input, one response)
    - Multi-turn journeys (conversation with state)
    - Workspace setup with files
    - Environment variable injection
    - Timeout and retry handling
    """

    def __init__(
        self,
        *,
        model: Any | None = None,
        provider: str = "ollama",
        model_name: str | None = None,
        trust_level: str = "shell",
        cleanup_workspace: bool = True,
        debug: bool = False,
        enable_sunwell_tools: bool = False,
    ) -> None:
        """Initialize the runner.

        Args:
            model: Pre-created model (if None, creates from provider/model_name)
            provider: Model provider if model not provided
            model_name: Model name if model not provided
            trust_level: Tool trust level
            cleanup_workspace: Whether to cleanup workspace after run
            debug: Enable debug logging
            enable_sunwell_tools: Enable Sunwell self-introspection tools (RFC-125)
        """
        self._model = model
        self._provider = provider
        self._model_name = model_name
        self._trust_level = trust_level
        self._cleanup_workspace = cleanup_workspace
        self._debug = debug
        self._enable_sunwell_tools = enable_sunwell_tools
        self._assertions = BehavioralAssertions()

    async def run(self, journey: Journey) -> JourneyResult:
        """Run a journey and return results.

        Args:
            journey: Journey to execute.

        Returns:
            JourneyResult with assertion outcomes.
        """
        start_time = time()
        retry_count = 0
        max_retries = journey.allow_flaky_retry

        while True:
            try:
                if journey.journey_type == JourneyType.SINGLE_TURN:
                    assert isinstance(journey, SingleTurnJourney)
                    result = await self._run_single_turn(journey)
                else:
                    assert isinstance(journey, MultiTurnJourney)
                    result = await self._run_multi_turn(journey)

                result.retry_count = retry_count
                result.duration_ms = int((time() - start_time) * 1000)

                # Check if we should retry
                if not result.passed and retry_count < max_retries:
                    logger.info(
                        "Journey %s failed, retrying (%d/%d)",
                        journey.id, retry_count + 1, max_retries
                    )
                    retry_count += 1
                    continue

                return result

            except asyncio.TimeoutError:
                return JourneyResult(
                    journey_id=journey.id,
                    passed=False,
                    error=f"Timeout after {journey.timeout_seconds}s",
                    duration_ms=int((time() - start_time) * 1000),
                    retry_count=retry_count,
                )
            except Exception as e:
                logger.exception("Journey %s failed with error", journey.id)
                return JourneyResult(
                    journey_id=journey.id,
                    passed=False,
                    error=str(e),
                    duration_ms=int((time() - start_time) * 1000),
                    retry_count=retry_count,
                )

    async def _run_single_turn(self, journey: SingleTurnJourney) -> JourneyResult:
        """Run a single-turn journey."""
        workspace = self._setup_workspace(journey.setup)

        try:
            # Create recorder and start capturing
            recorder = EventRecorder()
            recorder.start()

            try:
                # Execute the input
                output = await asyncio.wait_for(
                    self._execute_input(journey.input, workspace, recorder),
                    timeout=journey.timeout_seconds,
                )

                # Check assertions
                report = self._assertions.check_all(
                    recorder,
                    journey.expect,
                    workspace=workspace,
                )

                return JourneyResult(
                    journey_id=journey.id,
                    passed=report.passed,
                    turn_results=[TurnResult(
                        turn_index=0,
                        input=journey.input,
                        passed=report.passed,
                        assertion_report=report,
                        duration_ms=0,
                        output=output,
                    )],
                    assertion_report=report,
                    events=list(recorder.events),
                    workspace=str(workspace),
                )

            finally:
                recorder.stop()

        finally:
            if self._cleanup_workspace:
                self._cleanup(workspace)

    async def _run_multi_turn(self, journey: MultiTurnJourney) -> JourneyResult:
        """Run a multi-turn journey."""
        workspace = self._setup_workspace(journey.setup)

        try:
            # Create recorder - keep it running across turns
            recorder = EventRecorder()
            recorder.start()

            combined_report = AssertionReport()
            turn_results: list[TurnResult] = []
            all_passed = True

            try:
                # Create chat loop for multi-turn
                loop = await self._create_chat_loop(workspace)

                for i, turn in enumerate(journey.turns):
                    turn_start = time()

                    # Archive previous turn and start fresh (preserves history)
                    if i > 0:
                        recorder.new_turn()

                    # Execute turn
                    try:
                        output = await asyncio.wait_for(
                            self._execute_turn(loop, turn.input, recorder),
                            timeout=journey.timeout_seconds // len(journey.turns),
                        )
                    except asyncio.TimeoutError:
                        turn_results.append(TurnResult(
                            turn_index=i,
                            input=turn.input,
                            passed=False,
                            assertion_report=AssertionReport(),
                            duration_ms=int((time() - turn_start) * 1000),
                            error="Turn timeout",
                        ))
                        all_passed = False
                        continue

                    # Check assertions for this turn
                    turn_report = self._assertions.check_all(
                        recorder,
                        turn.expect,
                        workspace=workspace,
                    )

                    turn_passed = turn_report.passed
                    if not turn_passed:
                        all_passed = False

                    turn_results.append(TurnResult(
                        turn_index=i,
                        input=turn.input,
                        passed=turn_passed,
                        assertion_report=turn_report,
                        duration_ms=int((time() - turn_start) * 1000),
                        output=output,
                    ))

                    combined_report.merge(turn_report)

                return JourneyResult(
                    journey_id=journey.id,
                    passed=all_passed,
                    turn_results=turn_results,
                    assertion_report=combined_report,
                    events=recorder.all_events,  # Include events from all turns
                    workspace=str(workspace),
                )

            finally:
                recorder.stop()

        finally:
            if self._cleanup_workspace:
                self._cleanup(workspace)

    def _setup_workspace(self, setup: Setup) -> Path:
        """Create workspace directory with setup files."""
        # Generate workspace path
        workspace_template = setup.workspace
        workspace_path = workspace_template.replace("{uuid}", str(uuid.uuid4())[:8])
        workspace = Path(workspace_path)

        # Create directory
        workspace.mkdir(parents=True, exist_ok=True)

        # Create setup files
        for file_setup in setup.files:
            file_path = workspace / file_setup.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_setup.content)

        # Set environment variables
        for key, value in setup.env.items():
            os.environ[key] = value

        logger.debug("Workspace created: %s with %d files", workspace, len(setup.files))
        return workspace

    def _cleanup(self, workspace: Path) -> None:
        """Clean up workspace directory."""
        try:
            if workspace.exists():
                shutil.rmtree(workspace)
                logger.debug("Workspace cleaned up: %s", workspace)
        except Exception as e:
            logger.warning("Failed to cleanup workspace %s: %s", workspace, e)

    async def _get_model(self) -> Any:
        """Get or create the model."""
        if self._model is not None:
            return self._model

        # Lazy import to avoid circular dependencies
        from sunwell.foundation.config import get_config
        from sunwell.models import OllamaModel, OpenAIModel

        config = get_config()
        provider = self._provider or config.model.default_provider
        model_name = self._model_name or config.model.default_model

        # Create model based on provider
        if provider == "ollama":
            self._model = OllamaModel(model=model_name)
        elif provider == "openai":
            self._model = OpenAIModel(model=model_name)
        elif provider == "anthropic":
            from sunwell.models import AnthropicModel
            self._model = AnthropicModel(model=model_name)
        else:
            # Default to Ollama
            self._model = OllamaModel(model=model_name)

        return self._model

    async def _execute_input(
        self,
        user_input: str,
        workspace: Path,
        recorder: EventRecorder,
    ) -> str:
        """Execute a single input and return output.
        
        Always runs with tools available - the model decides whether to use them.
        This is simpler and more reliable than pre-classifying intent.
        """
        from sunwell.knowledge.project import (
            ProjectResolutionError,
            create_project_from_workspace,
            resolve_project,
        )
        from sunwell.tools.core.types import ToolPolicy, ToolTrust
        from sunwell.tools.execution import ToolExecutor

        model = await self._get_model()

        # Verbose: show model being used
        if self._debug:
            model_name = getattr(model, "model", getattr(model, "_model", "unknown"))
            _verbose_console.print(f"  [dim]Model: {model_name}[/dim]")
            _verbose_console.print(f"  [dim]Input: \"{user_input[:60]}{'...' if len(user_input) > 60 else ''}\"[/dim]")

        # Set up project and tools
        try:
            project = resolve_project(cwd=workspace)
        except ProjectResolutionError:
            project = create_project_from_workspace(workspace)

        policy = ToolPolicy(trust_level=ToolTrust.from_string(self._trust_level))

        # Set up optional handlers for advanced tools
        sunwell_handler = None
        if self._enable_sunwell_tools:
            from sunwell.tools.sunwell.handlers import SunwellToolHandlers
            sunwell_handler = SunwellToolHandlers(workspace=workspace)

        tool_executor = ToolExecutor(
            project=project,
            sandbox=None,
            policy=policy,
            sunwell_handler=sunwell_handler,
        )

        # Extract signals for routing/observability (but don't gate on them)
        from sunwell.agent.events import EventType
        from sunwell.agent.events.types import AgentEvent
        from sunwell.agent.signals import extract_signals

        signals = await extract_signals(user_input, model)

        # Record signals as event (for behavioral assertions)
        signals_event = AgentEvent(
            type=EventType.SIGNAL,
            data={
                "signal_type": "adaptive",
                "complexity": signals.complexity,
                "needs_tools": signals.needs_tools,
                "is_ambiguous": signals.is_ambiguous,
                "is_dangerous": signals.is_dangerous,
                "is_epic": signals.is_epic,
                "confidence": signals.confidence,
                "domain": signals.domain,
                "planning_route": signals.planning_route,
                "execution_route": signals.execution_route,
            },
        )
        recorder._handle_event(signals_event)

        # Also record intent as TASK (since we always run with tools)
        # The model will naturally respond conversationally if appropriate
        intent_event = AgentEvent(
            type=EventType.SIGNAL,
            data={
                "signal_type": "intent",
                "intent": "task",  # Always TASK - model decides tool use
                "confidence": 1.0,
                "reasoning": "Always run with tools available",
            },
        )
        recorder._handle_event(intent_event)

        if self._debug:
            _verbose_console.print(f"  [dim]Intent: [green]task[/green] (tools available, model decides)[/dim]")

        # Run agent loop with tools available
        # Decide tool_choice based on signal extraction
        from sunwell.agent import AgentLoop, LoopConfig

        # If signals indicate tools are needed, use tool_choice="auto" with strong hint
        # Otherwise let model decide freely
        tool_choice = "auto"
        if signals.needs_tools == "YES":
            # Strong hint in system prompt since we know tools are needed
            system_prompt = (
                "You are a helpful assistant with access to tools. "
                "The user's request requires using tools - do not try to answer from memory. "
                "Use the appropriate tool to get real, current information. "
                "For file operations, use file tools. For git, use git tools. "
                "For environment info, use list_env or run_command."
            )
        else:
            # More permissive - model decides
            system_prompt = (
                "You are a helpful assistant with access to tools. "
                "Use tools when they would help answer the user's request accurately. "
                "For factual questions about files, code, git, or the environment, prefer tools. "
                "For general knowledge or conversation, you may respond directly."
            )

        loop_config = LoopConfig(
            max_turns=20,
            tool_choice=tool_choice,
            enable_confidence_routing=False,  # Skip vortex/interference complexity
            enable_learning_injection=False,  # Simpler prompts
        )

        agent_loop = AgentLoop(
            model=model,
            executor=tool_executor,
            config=loop_config,
        )

        output_parts: list[str] = []
        tool_call_count = 0
        async for event in agent_loop.run(user_input, system_prompt=system_prompt):
            recorder._handle_event(event)
            
            # Verbose: show events as they happen
            if self._debug:
                if event.type == EventType.TOOL_START:
                    tool_name = event.data.get("tool_name", event.data.get("tool", "?"))
                    tool_call_count += 1
                    _verbose_console.print(f"    [cyan]→ Tool: {tool_name}[/cyan]")
                elif event.type == EventType.TOOL_COMPLETE:
                    tool_name = event.data.get("tool_name", event.data.get("tool", "?"))
                    _verbose_console.print(f"    [green]✓ {tool_name} complete[/green]")
                elif event.type == EventType.TOOL_ERROR:
                    error = event.data.get("error", "unknown error")[:50]
                    _verbose_console.print(f"    [red]✗ Tool error: {error}[/red]")
                
            # Collect output from completion events
            if hasattr(event, "data") and event.data:
                if "output" in event.data:
                    output_parts.append(str(event.data["output"]))
                elif "content" in event.data:
                    output_parts.append(str(event.data["content"]))

        # Verbose: summary
        if self._debug:
            _verbose_console.print(f"  [dim]Tool calls: {tool_call_count}, Events: {len(recorder.events)}, Recorded tools: {len(recorder.tool_calls)}[/dim]")

        return "\n".join(output_parts) if output_parts else ""

    async def _create_chat_loop(self, workspace: Path) -> Any:
        """Create a chat loop for multi-turn conversations."""
        from sunwell.agent.chat import UnifiedChatLoop
        from sunwell.knowledge.project import (
            ProjectResolutionError,
            create_project_from_workspace,
            resolve_project,
        )
        from sunwell.tools.core.types import ToolPolicy, ToolTrust
        from sunwell.tools.execution import ToolExecutor

        model = await self._get_model()

        try:
            project = resolve_project(cwd=workspace)
        except ProjectResolutionError:
            project = create_project_from_workspace(workspace)

        policy = ToolPolicy(trust_level=ToolTrust.from_string(self._trust_level))
        tool_executor = ToolExecutor(
            project=project,
            sandbox=None,
            policy=policy,
        )

        return UnifiedChatLoop(
            model=model,
            tool_executor=tool_executor,
            workspace=workspace,
            auto_confirm=True,  # Auto-confirm for testing
            stream_progress=True,
        )

    async def _execute_turn(
        self,
        loop: Any,
        user_input: str,
        recorder: EventRecorder,
    ) -> str:
        """Execute a single turn in a multi-turn conversation."""
        # For now, use the single input execution
        # In future, this should use the actual chat loop generator
        return await self._execute_input(user_input, loop.workspace, recorder)


async def run_journeys(
    journeys: list[Journey],
    *,
    parallel: bool = False,
    max_concurrent: int = 4,
    **runner_kwargs: Any,
) -> list[JourneyResult]:
    """Run multiple journeys.

    Args:
        journeys: List of journeys to run.
        parallel: Run journeys in parallel.
        max_concurrent: Maximum concurrent journeys.
        **runner_kwargs: Arguments passed to JourneyRunner.

    Returns:
        List of JourneyResults in same order as input.
    """
    runner = JourneyRunner(**runner_kwargs)

    if parallel:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_with_semaphore(j: Journey) -> JourneyResult:
            async with semaphore:
                return await runner.run(j)

        return await asyncio.gather(*[run_with_semaphore(j) for j in journeys])
    else:
        return [await runner.run(j) for j in journeys]
