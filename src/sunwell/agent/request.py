"""RunRequest — Input contract for Agent.run() (RFC-110).

The RunRequest encapsulates everything needed to execute a goal:
- The goal itself (natural language, shortcuts already expanded)
- Context (target files, workspace state, user preferences)
- Options (trust level, timeout, validation settings)
- Optional lens for expertise injection

Example:
    >>> request = RunRequest(
    ...     goal="Build a REST API with auth",
    ...     context={"target_files": ["api.py"]},
    ...     options=RunOptions(trust=ToolTrust.WORKSPACE),
    ... )
    >>> async for event in agent.run(request):
    ...     handle(event)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.convergence import ConvergenceConfig


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Execution configuration for Agent.run().

    Controls trust levels, timeouts, and feature flags.
    """

    trust: str = "workspace"
    """Tool trust level: 'read_only', 'workspace', or 'shell'."""

    timeout_seconds: int = 300
    """Maximum execution time in seconds."""

    max_tokens: int = 50_000
    """Maximum token budget for this run."""

    streaming: bool = True
    """Whether to stream events during execution."""

    validate: bool = True
    """Whether to run validation gates."""

    persist_learnings: bool = True
    """Whether to save learnings to Simulacrum."""

    auto_fix: bool = True
    """Whether to attempt auto-fix on errors."""

    max_fix_attempts: int = 3
    """Maximum fix attempts per error."""

    enable_briefing: bool = True
    """Whether to load/save briefings for session continuity."""

    enable_prefetch: bool = True
    """Whether to pre-load context based on briefing signals."""

    prefetch_timeout: float = 2.0
    """Maximum time to wait for prefetch (seconds)."""

    # RFC-123: Convergence loops
    converge: bool = False
    """Enable convergence loops after file writes."""

    convergence_config: ConvergenceConfig | None = None
    """Custom convergence configuration (uses defaults if None)."""

    def with_trust(self, trust: str) -> RunOptions:
        """Return options with updated trust level."""
        return RunOptions(
            trust=trust,
            timeout_seconds=self.timeout_seconds,
            max_tokens=self.max_tokens,
            streaming=self.streaming,
            validate=self.validate,
            persist_learnings=self.persist_learnings,
            auto_fix=self.auto_fix,
            max_fix_attempts=self.max_fix_attempts,
            enable_briefing=self.enable_briefing,
            enable_prefetch=self.enable_prefetch,
            prefetch_timeout=self.prefetch_timeout,
            converge=self.converge,
            convergence_config=self.convergence_config,
        )


@dataclass(frozen=True, slots=True)
class RunRequest:
    """Input to Agent.run() — everything needed to execute a goal.

    This is THE contract for agent execution. All entry points
    (CLI, chat, Studio) construct a RunRequest and call Agent.run().

    Attributes:
        goal: Natural language goal (shortcuts already expanded by CLI)
        context: Injected context dict (target files, workspace state, etc.)
        lens: Explicit lens or None for auto-selection
        options: Execution options (trust, timeout, etc.)
        cwd: Working directory (defaults to current directory)
        session: Optional Simulacrum session name for persistence
    """

    goal: str
    """Natural language goal (shortcuts already expanded)."""

    context: dict[str, Any] = field(default_factory=dict)
    """Injected context: target files, workspace state, user preferences."""

    lens: Any = None  # Lens | None, avoiding import
    """Explicit lens or None for auto-selection."""

    options: RunOptions = field(default_factory=RunOptions)
    """Execution options (trust, timeout, etc.)."""

    cwd: Path | None = None
    """Working directory. Defaults to Path.cwd() if None."""

    session: str | None = None
    """Simulacrum session name for cross-session memory."""

    def with_context(self, **kwargs: Any) -> RunRequest:
        """Return request with additional context."""
        return RunRequest(
            goal=self.goal,
            context={**self.context, **kwargs},
            lens=self.lens,
            options=self.options,
            cwd=self.cwd,
            session=self.session,
        )

    def with_lens(self, lens: Any) -> RunRequest:
        """Return request with explicit lens."""
        return RunRequest(
            goal=self.goal,
            context=self.context,
            lens=lens,
            options=self.options,
            cwd=self.cwd,
            session=self.session,
        )

    def with_options(self, **kwargs: Any) -> RunRequest:
        """Return request with updated options."""
        current = self.options
        new_options = RunOptions(
            trust=kwargs.get("trust", current.trust),
            timeout_seconds=kwargs.get("timeout_seconds", current.timeout_seconds),
            max_tokens=kwargs.get("max_tokens", current.max_tokens),
            streaming=kwargs.get("streaming", current.streaming),
            validate=kwargs.get("validate", current.validate),
            persist_learnings=kwargs.get("persist_learnings", current.persist_learnings),
            auto_fix=kwargs.get("auto_fix", current.auto_fix),
            max_fix_attempts=kwargs.get("max_fix_attempts", current.max_fix_attempts),
            enable_briefing=kwargs.get("enable_briefing", current.enable_briefing),
            enable_prefetch=kwargs.get("enable_prefetch", current.enable_prefetch),
            prefetch_timeout=kwargs.get("prefetch_timeout", current.prefetch_timeout),
            converge=kwargs.get("converge", current.converge),
            convergence_config=kwargs.get("convergence_config", current.convergence_config),
        )
        return RunRequest(
            goal=self.goal,
            context=self.context,
            lens=self.lens,
            options=new_options,
            cwd=self.cwd,
            session=self.session,
        )
