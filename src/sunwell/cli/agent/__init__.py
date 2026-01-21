"""CLI commands for Agent Mode (RFC-032, RFC-037).

This package provides the 'sunwell agent' command group.
Renamed from 'naaru' for clarity (RFC-037).

Provides:
- sunwell agent run "goal": Execute arbitrary tasks (same as bare 'sunwell "goal"')
- sunwell agent resume: Resume from checkpoint
- sunwell agent illuminate: Self-improvement mode (RFC-019)
- sunwell agent status: Show agent state
- sunwell agent plans: Manage saved plans (RFC-040)
- sunwell agent benchmark: Agent benchmarks
"""

import click

from sunwell.cli.agent.benchmark import agent_benchmark
from sunwell.cli.agent.illuminate import illuminate
from sunwell.cli.agent.plans import plans_cmd
from sunwell.cli.agent.resume import resume
from sunwell.cli.agent.run import run
from sunwell.cli.agent.status import status

console = None  # Will be imported from run module


@click.group()
def agent() -> None:
    """Agent commands for task execution and management.

    For most use cases, you can skip this command group entirely:

    \b
        sunwell "Build a REST API"          # Same as: sunwell agent run "..."
        sunwell "Build an app" --plan       # Same as: sunwell agent run "..." --dry-run

    The agent command group is for advanced operations like resuming
    interrupted runs or running self-improvement mode.
    """
    pass


# Register all commands
agent.add_command(run)
agent.add_command(resume)
agent.add_command(illuminate)
agent.add_command(status)
agent.add_command(plans_cmd)
agent.add_command(agent_benchmark)

__all__ = ["agent"]
