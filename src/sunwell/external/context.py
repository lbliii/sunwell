"""External Context for RFC-042 Integration (RFC-049).

Wrapper for external context when routing through the Adaptive Agent.
"""

from dataclasses import dataclass

from sunwell.external.types import EventSource


@dataclass(frozen=True, slots=True)
class ExternalContext:
    """External context for adaptive routing (RFC-042 integration).

    Provides additional context when a goal originates from an external event,
    without modifying the core AdaptiveSignals dataclass.
    """

    is_external_goal: bool = False
    """Whether this goal originated from an external event."""

    external_source: EventSource | None = None
    """Source of the external event (github, linear, etc.)."""

    external_priority: float = 0.5
    """Priority hint from external event."""

    ci_logs: str | None = None
    """CI failure logs if available (for CI failure goals)."""

    issue_body: str | None = None
    """Issue body if this is an issue-triggered goal."""

    error_message: str | None = None
    """Error message if this is an alert-triggered goal."""

    def with_ci_logs(self, logs: str) -> ExternalContext:
        """Return a new context with CI logs added.

        Args:
            logs: CI logs to add

        Returns:
            New ExternalContext with logs
        """
        return ExternalContext(
            is_external_goal=self.is_external_goal,
            external_source=self.external_source,
            external_priority=self.external_priority,
            ci_logs=logs,
            issue_body=self.issue_body,
            error_message=self.error_message,
        )

    def with_issue_body(self, body: str) -> ExternalContext:
        """Return a new context with issue body added.

        Args:
            body: Issue body to add

        Returns:
            New ExternalContext with issue body
        """
        return ExternalContext(
            is_external_goal=self.is_external_goal,
            external_source=self.external_source,
            external_priority=self.external_priority,
            ci_logs=self.ci_logs,
            issue_body=body,
            error_message=self.error_message,
        )

    @classmethod
    def from_event(cls, source: EventSource, priority: float) -> ExternalContext:
        """Create context from an external event.

        Args:
            source: Event source
            priority: Priority hint

        Returns:
            New ExternalContext
        """
        return cls(
            is_external_goal=True,
            external_source=source,
            external_priority=priority,
        )
