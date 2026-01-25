"""CLI commands for Agent Mode (RFC-032, RFC-037, RFC-MEMORY).

This package provides the 'sunwell agent' command group.

NOTE: 'sunwell agent run' was DELETED in RFC-MEMORY refactor.
Use 'sunwell run "goal"' instead (cli/main.py).

Provides:
- sunwell agent resume: Resume from checkpoint
- sunwell agent illuminate: Self-improvement mode
- sunwell agent status: Show agent state
- sunwell agent plans: Manage saved plans
- sunwell agent benchmark: Agent benchmarks
"""

import click

from sunwell.interface.cli.commands.agent.benchmark import agent_benchmark
from sunwell.interface.cli.commands.agent.illuminate import illuminate
from sunwell.interface.cli.commands.agent.plans import plans_cmd
from sunwell.interface.cli.commands.agent.resume import resume
from sunwell.interface.cli.commands.agent.status import status


@click.group()
def agent() -> None:
    """Agent commands for task execution and management.

    For running goals, use the main command:

    \b
        sunwell run "Build a REST API"
        sunwell run "Build an app" --plan

    The agent command group is for advanced operations like resuming
    interrupted runs or running self-improvement mode.
    """
    pass


# Register commands (run was removed - use 'sunwell run' instead)
agent.add_command(resume)
agent.add_command(illuminate)
agent.add_command(status)
agent.add_command(plans_cmd)
agent.add_command(agent_benchmark)

__all__ = ["agent"]
