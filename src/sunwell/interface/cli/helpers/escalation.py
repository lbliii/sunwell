"""CLI Escalation UI for Autonomous Mode.

Implements UIProtocol for interactive escalation prompts in the terminal.
"""

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table


@dataclass(slots=True)
class CLIEscalationUI:
    """CLI implementation of UIProtocol for escalation prompts.

    Provides interactive prompts for handling escalations during
    autonomous backlog execution.

    Example:
        >>> ui = CLIEscalationUI(console)
        >>> guardrails.escalation_handler.ui = ui
        >>> resolution = await guardrails.escalate_goal(goal)
    """

    console: Console
    """Rich console for output."""

    _last_escalation: dict | None = None
    """Cache for view command."""

    async def show_escalation(
        self,
        severity: str,
        message: str,
        options: list[dict],
        recommended: str,
    ) -> None:
        """Show escalation to user with Rich formatting.

        Args:
            severity: Escalation severity (info, warning, critical)
            message: Human-readable escalation message
            options: List of option dicts with id, label, description
            recommended: ID of recommended option
        """
        # Store for view command
        self._last_escalation = {
            "severity": severity,
            "message": message,
            "options": options,
            "recommended": recommended,
        }

        # Determine style based on severity
        style_map = {
            "critical": "red bold",
            "warning": "yellow",
            "info": "cyan",
        }
        style = style_map.get(severity, "white")

        # Show escalation panel
        self.console.print()
        self.console.print(
            Panel(
                message,
                title=f"[{style}]Requires Approval[/]",
                border_style=style,
            )
        )

    async def await_escalation_response(self, escalation_id: str) -> dict:
        """Await user's response to escalation.

        Args:
            escalation_id: ID of the escalation

        Returns:
            Dict with option_id and action
        """
        # Show options
        self.console.print()
        self.console.print(
            "[bold]Options:[/] "
            "[a]pprove  [s]kip  [S]kip-all  [v]iew-details  [q]uit"
        )

        while True:
            choice = Prompt.ask(
                "Choice",
                choices=["a", "s", "S", "v", "q"],
                default="s",
            )

            match choice:
                case "a":
                    return {"option_id": "approve", "action": "approve"}
                case "s":
                    return {"option_id": "skip", "action": "skip"}
                case "S":
                    return {"option_id": "skip_all", "action": "skip_all"}
                case "v":
                    self._show_details()
                    # Loop back to prompt
                case "q":
                    return {"option_id": "abort", "action": "abort"}

    def _show_details(self) -> None:
        """Show detailed escalation information."""
        if not self._last_escalation:
            self.console.print("[dim]No details available[/dim]")
            return

        self.console.print()
        self.console.print(Panel(
            self._last_escalation["message"],
            title="Escalation Details",
        ))

        # Show options table
        table = Table(title="Available Actions")
        table.add_column("Key", style="bold")
        table.add_column("Action")
        table.add_column("Description")

        table.add_row("a", "Approve", "Execute this goal")
        table.add_row("s", "Skip", "Skip this goal, continue to next")
        table.add_row("S", "Skip All", "Skip all remaining escalations")
        table.add_row("q", "Quit", "End autonomous session")

        self.console.print(table)
        self.console.print()


def create_cli_escalation_ui(console: Console) -> CLIEscalationUI:
    """Create a CLI escalation UI.

    Args:
        console: Rich console for output

    Returns:
        Configured CLIEscalationUI instance
    """
    return CLIEscalationUI(console=console)
